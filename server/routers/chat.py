"""Chat and message routes."""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.genai import types
from sqlmodel import Session, select

from server.database import get_session
from server.models import ChatMessage as DBMessage
from server.schemas import ChatRequest
from server.services import gemini_service
from server.services.gemini_service import (
    SYSTEM_PROMPT,
    generate_stream,
    generate_with_retry_and_fallback,
)
from server.services.rag_service import RAGService

from server.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Initialize RAG service
try:
    rag_service: RAGService | None = RAGService()
    logger.info(
        "RAG service initialized",
        extra={"document_count": rag_service.chroma_collection.count()},
    )
except Exception as e:
    logger.warning("RAG service failed to initialize", exc_info=e)
    rag_service = None


@router.get("/messages")
def get_messages(session_id: str = "default", db: Session = Depends(get_session)):
    messages = db.exec(
        select(DBMessage)
        .where(DBMessage.session_id == session_id)
        .order_by(DBMessage.timestamp)
    ).all()
    res = []
    for m in messages:
        sources_list = json.loads(m.sources) if m.sources else []
        res.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "sources": sources_list,
        })
    return res


@router.delete("/messages")
def clear_messages(session_id: str = "default", db: Session = Depends(get_session)):
    messages = db.exec(select(DBMessage).where(DBMessage.session_id == session_id)).all()
    for m in messages:
        db.delete(m)
    db.commit()
    return {"status": "ok"}


@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_session)):
    if not gemini_service.client:
        raise HTTPException(status_code=500, detail="API key not configured")

    # --- Step 1: Retrieve RAG context ---
    context_block, sources, no_context = _build_rag_context(request.message)

    # --- Step 2: Build prompt ---
    contents = _build_contents(request.message, context_block, request.history)

    # --- Step 3: Generate with timeout + retry + fallback ---
    response = await generate_with_retry_and_fallback(contents)

    # --- Step 4: Persist messages (isolated from response) ---
    bot_id, db_error = _persist_messages(
        db=db,
        message_id=request.message_id,
        session_id=request.session_id,
        user_content=request.message,
        assistant_content=response.text,
        sources=sources,
    )

    # --- Step 5: Return response (even if DB failed) ---
    result = {
        "id": bot_id,
        "reply": response.text,
        "sources": sources,
        "no_context": no_context,
    }
    if db_error:
        result["warning"] = "Message generated but could not be saved to history."

    return result


def _persist_messages(
    db: Session,
    message_id: str,
    session_id: str,
    user_content: str,
    assistant_content: str,
    sources: list,
) -> tuple[str, str | None]:
    """Persist user and assistant messages to the database.

    Returns (bot_id, db_error). db_error is None on success.
    """
    bot_id = str(uuid.uuid4())
    db_error = None
    try:
        user_msg = DBMessage(
            id=message_id,
            session_id=session_id,
            role="user",
            content=user_content,
            timestamp=int(time.time() * 1000),
        )
        db.add(user_msg)

        bot_msg = DBMessage(
            id=bot_id,
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            timestamp=int(time.time() * 1000) + 1,
            sources=json.dumps(sources) if sources else None,
        )
        db.add(bot_msg)
        db.commit()
    except Exception as e:
        logger.error("Failed to persist messages", exc_info=e, extra={"session_id": session_id})
        db_error = str(e)
        try:
            db.rollback()
        except Exception:
            pass

    return bot_id, db_error


def _build_rag_context(message: str) -> tuple[str, list, bool]:
    """Retrieve RAG context. Returns (context_block, sources, no_context)."""
    sources: list = []
    context_block = ""
    no_context = False

    if rag_service and rag_service.chroma_collection.count() > 0:
        rag_result = rag_service.query(message)
        context_block = rag_result["context"]
        sources = rag_result["sources"]

    if not context_block.strip():
        no_context = True

    return context_block, sources, no_context


def _build_contents(message: str, context_block: str, history: list) -> list:
    """Build the Gemini contents array from message, context, and history."""
    user_content = message
    if context_block:
        user_content = (
            f"Context from MOE policy documents:\n\n{context_block}\n\n"
            f"---\n\nUser question: {message}"
        )

    contents = [types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT)])]
    contents.append(
        types.Content(
            role="model",
            parts=[
                types.Part(
                    text="Understood. I will answer based on MOE policy documents and cite sources."
                )
            ],
        )
    )

    for msg in history:
        role = "user" if msg.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    contents.append(types.Content(role="user", parts=[types.Part(text=user_content)]))
    return contents


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_session)):
    """SSE streaming endpoint. Sends token chunks as they arrive from Gemini.

    Event types:
    - data: {"token": "..."} — a text chunk
    - data: {"sources": [...], "no_context": bool} — metadata (sent first)
    - data: {"done": true, "id": "..."} — stream complete
    - data: {"error": "..."} — error occurred
    """
    if not gemini_service.client:
        raise HTTPException(status_code=500, detail="API key not configured")

    # Retrieve RAG context (synchronous, fast)
    context_block, sources, no_context = _build_rag_context(request.message)
    contents = _build_contents(request.message, context_block, request.history)

    async def event_generator():
        # Send metadata first
        meta = json.dumps({"sources": sources, "no_context": no_context})
        yield f"data: {meta}\n\n"

        full_text = ""
        try:
            async for chunk in generate_stream(contents):
                full_text += chunk
                token_event = json.dumps({"token": chunk})
                yield f"data: {token_event}\n\n"
        except HTTPException as e:
            error_event = json.dumps({"error": e.detail})
            yield f"data: {error_event}\n\n"
            return
        except Exception as e:
            error_event = json.dumps({"error": str(e)})
            yield f"data: {error_event}\n\n"
            return

        # Persist messages after streaming completes
        bot_id, db_error = _persist_messages(
            db=db,
            message_id=request.message_id,
            session_id=request.session_id,
            user_content=request.message,
            assistant_content=full_text,
            sources=sources,
        )

        # Send done event
        done_data: dict = {"done": True, "id": bot_id}
        if db_error:
            done_data["warning"] = "Message generated but could not be saved to history."
        yield f"data: {json.dumps(done_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
