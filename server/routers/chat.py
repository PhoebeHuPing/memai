"""Chat and message routes."""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from google.genai import types
from sqlmodel import Session, select

from server.database import get_session
from server.models import ChatMessage as DBMessage
from server.schemas import ChatRequest
from server.services import gemini_service
from server.services.gemini_service import (
    SYSTEM_PROMPT,
    generate_with_retry_and_fallback,
)
from server.services.rag_service import RAGService

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Initialize RAG service
try:
    rag_service: RAGService | None = RAGService()
    print(
        f"RAG service initialized. Collection has {rag_service.chroma_collection.count()} documents."
    )
except Exception as e:
    print(f"Warning: RAG service failed to initialize: {e}")
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
    sources: list = []
    context_block = ""
    no_context = False

    if rag_service and rag_service.chroma_collection.count() > 0:
        rag_result = rag_service.query(request.message)
        context_block = rag_result["context"]
        sources = rag_result["sources"]

    # Mark when RAG found nothing useful
    if not context_block.strip():
        no_context = True

    # --- Step 2: Build prompt ---
    user_content = request.message
    if context_block:
        user_content = (
            f"Context from MOE policy documents:\n\n{context_block}\n\n"
            f"---\n\nUser question: {request.message}"
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

    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    contents.append(types.Content(role="user", parts=[types.Part(text=user_content)]))

    # --- Step 3: Generate with timeout + retry + fallback ---
    response = await generate_with_retry_and_fallback(contents)

    # --- Step 4: Persist messages (isolated from response) ---
    db_error = None
    try:
        user_msg = DBMessage(
            id=request.message_id,
            session_id=request.session_id,
            role="user",
            content=request.message,
            timestamp=int(time.time() * 1000),
        )
        db.add(user_msg)

        bot_id = str(uuid.uuid4())
        bot_msg = DBMessage(
            id=bot_id,
            session_id=request.session_id,
            role="assistant",
            content=response.text,
            timestamp=int(time.time() * 1000) + 1,
            sources=json.dumps(sources) if sources else None,
        )
        db.add(bot_msg)
        db.commit()
    except Exception as e:
        print(f"[DB Error] Failed to persist messages: {e}")
        db_error = str(e)
        bot_id = str(uuid.uuid4())
        try:
            db.rollback()
        except Exception:
            pass

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
