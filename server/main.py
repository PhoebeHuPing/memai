import os
from typing import List, Optional
import time
import json
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PydanticField
from pydantic import field_validator
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sqlmodel import Session, select
from server.database import create_db_and_tables, get_session
from server.models import ChatMessage as DBMessage, ChatSession

load_dotenv()

api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
if not api_key:
    print("Warning: GOOGLE_GENERATIVE_AI_API_KEY not found")
    client = None
else:
    client = genai.Client(api_key=api_key)

gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
print(f"Gemini model configured: {gemini_model}")

# Fallback models in case of temporary 429 (quota) or 503 (demand) errors
fallback_models = []
if gemini_model:
    fallback_models.append(gemini_model)
for model_candidate in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"]:
    if model_candidate not in fallback_models:
        fallback_models.append(model_candidate)
print(f"Model fallback chain: {fallback_models}")

# --- Configuration ---
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_RETRY_BASE_DELAY = float(os.getenv("GEMINI_RETRY_BASE_DELAY", "1.0"))

# Initialize RAG service
from server.services.rag_service import RAGService
try:
    rag_service = RAGService()
    print(f"RAG service initialized. Collection has {rag_service.chroma_collection.count()} documents.")
except Exception as e:
    print(f"Warning: RAG service failed to initialize: {e}")
    rag_service = None

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Unified Error Response ---
class ErrorResponse(BaseModel):
    """Unified error response returned to the frontend."""
    error_code: str
    message: str
    detail: Optional[str] = None


@app.exception_handler(HTTPException)
async def unified_http_exception_handler(request: Request, exc: HTTPException):
    """Convert all HTTPExceptions to a consistent ErrorResponse format."""
    error_code = _status_to_error_code(exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=error_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unified_generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="internal_error",
            message="An unexpected error occurred. Please try again.",
            detail=str(exc) if os.getenv("DEBUG") else None,
        ).model_dump(),
    )


def _status_to_error_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        404: "not_found",
        408: "timeout",
        429: "rate_limited",
        500: "internal_error",
        503: "service_unavailable",
    }
    return mapping.get(status_code, f"http_{status_code}")


# --- Helpers ---
def _is_retryable_error(exc: Exception) -> bool:
    """Check if an exception indicates a retryable condition (429/503)."""
    exc_str = str(exc).lower()
    # Google GenAI SDK raises google.api_core.exceptions or similar
    if "429" in exc_str or "resource exhausted" in exc_str:
        return True
    if "503" in exc_str or "service unavailable" in exc_str or "overloaded" in exc_str:
        return True
    return False


async def _generate_with_timeout(model_name: str, contents: list) -> object:
    """Call Gemini generate_content with a timeout.
    
    The Google GenAI SDK client.models.generate_content is synchronous,
    so we run it in an executor and wrap with asyncio.wait_for for timeout.
    """
    loop = asyncio.get_event_loop()

    async def _call():
        return await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(model=model_name, contents=contents),
        )

    return await asyncio.wait_for(_call(), timeout=GEMINI_TIMEOUT_SECONDS)


async def _generate_with_retry_and_fallback(contents: list) -> object:
    """Try each model in the fallback chain with per-model exponential backoff retries.
    
    For each model:
    - On retryable errors (429/503): retry up to GEMINI_MAX_RETRIES times with exponential backoff.
    - On timeout: move to the next model immediately (no retry).
    - On other errors: move to the next model immediately.
    
    Raises HTTPException if all models exhausted.
    """
    tried_models = []
    last_error = None

    for model_name in fallback_models:
        for attempt in range(GEMINI_MAX_RETRIES + 1):
            try:
                print(f"Attempting model={model_name}, attempt={attempt + 1}/{GEMINI_MAX_RETRIES + 1}")
                response = await _generate_with_timeout(model_name, contents)
                print(f"Successfully generated with model: {model_name}")
                return response
            except asyncio.TimeoutError:
                print(f"Timeout: model={model_name} did not respond within {GEMINI_TIMEOUT_SECONDS}s")
                last_error = TimeoutError(f"Model {model_name} timed out after {GEMINI_TIMEOUT_SECONDS}s")
                tried_models.append(model_name)
                break  # Don't retry timeouts, move to next model
            except Exception as e:
                last_error = e
                if _is_retryable_error(e) and attempt < GEMINI_MAX_RETRIES:
                    delay = GEMINI_RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"Retryable error on {model_name} (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    print(f"Non-retryable or exhausted retries for {model_name}: {e}")
                    tried_models.append(model_name)
                    break

    # All models failed
    if isinstance(last_error, TimeoutError):
        raise HTTPException(
            status_code=408,
            detail=f"All models timed out. Tried: {', '.join(tried_models)}"
        )
    elif last_error and _is_retryable_error(last_error):
        raise HTTPException(
            status_code=429,
            detail=f"Service is busy. All models ({', '.join(tried_models)}) returned rate limit or overload errors."
        )
    else:
        raise HTTPException(
            status_code=503,
            detail=f"All models ({', '.join(tried_models)}) failed. Last error: {str(last_error)}"
        )


SYSTEM_PROMPT = """You are MemAI, a specialist assistant for New Zealand school property management.
You answer questions based on MOE (Ministry of Education) policy documents.

Rules:
- Base your answers on the provided context from MOE documents.
- Always cite your sources with the document name and page number.
- If the context doesn't contain enough information, say so clearly.
- Use NZ-specific terminology (5YA, 10YPP, SFIS, etc.) naturally.
- Format responses in Markdown for readability."""


class Message(BaseModel):
    id: Optional[str] = None
    role: str
    content: str = PydanticField(max_length=50000)
    timestamp: Optional[int] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v


class ChatRequest(BaseModel):
    message_id: str = PydanticField(max_length=100)
    message: str = PydanticField(min_length=1, max_length=10000)
    history: List[Message] = PydanticField(default=[], max_length=100)
    session_id: str = PydanticField(default="default", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")


class RenameSessionRequest(BaseModel):
    title: str = PydanticField(min_length=1, max_length=60)


@app.get("/api/v1/sessions")
def list_sessions(db: Session = Depends(get_session)):
    """Return all session IDs with their last activity timestamp and title."""
    from sqlalchemy import func

    msg_stats = (
        select(
            DBMessage.session_id,
            func.max(DBMessage.timestamp).label("last_active"),
            func.min(
                func.case(
                    (DBMessage.role == "user", DBMessage.timestamp),
                    else_=None,
                )
            ).label("first_user_ts"),
        )
        .group_by(DBMessage.session_id)
        .subquery()
    )

    results = db.exec(
        select(
            msg_stats.c.session_id,
            msg_stats.c.last_active,
            ChatSession.title,
        )
        .outerjoin(ChatSession, ChatSession.id == msg_stats.c.session_id)
        .order_by(msg_stats.c.last_active.desc())
    ).all()

    sessions_needing_title = [r[0] for r in results if not r[2]]

    first_messages = {}
    if sessions_needing_title:
        for sid in sessions_needing_title:
            first_msg = db.exec(
                select(DBMessage.content)
                .where(DBMessage.session_id == sid, DBMessage.role == "user")
                .order_by(DBMessage.timestamp)
            ).first()
            first_messages[sid] = first_msg[:40] if first_msg else "New Chat"

    sessions = []
    for session_id, last_active, custom_title in results:
        title = custom_title if custom_title else first_messages.get(session_id, "New Chat")
        sessions.append({
            "session_id": session_id,
            "title": title,
            "last_active": last_active,
        })
    return sessions


@app.patch("/api/v1/sessions/{session_id}")
def rename_session(session_id: str, request: RenameSessionRequest, db: Session = Depends(get_session)):
    """Rename a session. Creates a ChatSession record if it doesn't exist."""
    chat_session = db.get(ChatSession, session_id)
    if chat_session:
        chat_session.title = request.title
    else:
        msg = db.exec(select(DBMessage).where(DBMessage.session_id == session_id)).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Session not found")
        chat_session = ChatSession(id=session_id, title=request.title, created_at=int(time.time() * 1000))
        db.add(chat_session)
    db.commit()
    return {"status": "ok", "session_id": session_id, "title": request.title}


@app.delete("/api/v1/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_session)):
    """Delete a session and all its messages."""
    messages = db.exec(select(DBMessage).where(DBMessage.session_id == session_id)).all()
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found")
    for m in messages:
        db.delete(m)
    chat_session = db.get(ChatSession, session_id)
    if chat_session:
        db.delete(chat_session)
    db.commit()
    return {"status": "ok"}


@app.get("/api/v1/messages")
def get_messages(session_id: str = "default", db: Session = Depends(get_session)):
    messages = db.exec(select(DBMessage).where(DBMessage.session_id == session_id).order_by(DBMessage.timestamp)).all()
    res = []
    for m in messages:
        sources_list = json.loads(m.sources) if m.sources else []
        res.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "sources": sources_list
        })
    return res

@app.delete("/api/v1/messages")
def clear_messages(session_id: str = "default", db: Session = Depends(get_session)):
    messages = db.exec(select(DBMessage).where(DBMessage.session_id == session_id)).all()
    for m in messages:
        db.delete(m)
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_session)):
    if not client:
        raise HTTPException(status_code=500, detail="API key not configured")

    # --- Step 1: Retrieve RAG context ---
    sources = []
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
    contents.append(types.Content(role="model", parts=[types.Part(text="Understood. I will answer based on MOE policy documents and cite sources.")]))

    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    contents.append(types.Content(role="user", parts=[types.Part(text=user_content)]))

    # --- Step 3: Generate with timeout + retry + fallback ---
    response = await _generate_with_retry_and_fallback(contents)

    # --- Step 4: Persist messages (isolated from response) ---
    db_error = None
    try:
        user_msg = DBMessage(
            id=request.message_id,
            session_id=request.session_id,
            role="user",
            content=request.message,
            timestamp=int(time.time() * 1000)
        )
        db.add(user_msg)

        bot_id = str(uuid.uuid4())
        bot_msg = DBMessage(
            id=bot_id,
            session_id=request.session_id,
            role="assistant",
            content=response.text,
            timestamp=int(time.time() * 1000) + 1,
            sources=json.dumps(sources) if sources else None
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
