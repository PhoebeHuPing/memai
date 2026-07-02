import os
from typing import List, Optional
import time
import json
import uuid
from fastapi import FastAPI, HTTPException, Depends
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
    results = db.exec(
        select(DBMessage.session_id, func.max(DBMessage.timestamp).label("last_active"))
        .group_by(DBMessage.session_id)
        .order_by(func.max(DBMessage.timestamp).desc())
    ).all()
    sessions = []
    for session_id, last_active in results:
        # Check if there's a custom title in the sessions table
        chat_session = db.get(ChatSession, session_id)
        if chat_session and chat_session.title:
            title = chat_session.title
        else:
            # Fallback: first user message as title
            first_msg = db.exec(
                select(DBMessage)
                .where(DBMessage.session_id == session_id, DBMessage.role == "user")
                .order_by(DBMessage.timestamp)
            ).first()
            title = first_msg.content[:40] if first_msg else "New Chat"
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
        # Verify session has messages
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
    # Delete all messages for this session
    messages = db.exec(select(DBMessage).where(DBMessage.session_id == session_id)).all()
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found")
    for m in messages:
        db.delete(m)
    # Delete session record if exists
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

    try:
        # Retrieve relevant context from RAG
        sources = []
        context_block = ""
        if rag_service and rag_service.chroma_collection.count() > 0:
            rag_result = rag_service.query(request.message)
            context_block = rag_result["context"]
            sources = rag_result["sources"]

        # Build prompt with RAG context
        user_content = request.message
        if context_block:
            user_content = (
                f"Context from MOE policy documents:\n\n{context_block}\n\n"
                f"---\n\nUser question: {request.message}"
            )

        # Build conversation history
        contents = [types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT)])]
        contents.append(types.Content(role="model", parts=[types.Part(text="Understood. I will answer based on MOE policy documents and cite sources.")]))

        for msg in request.history:
            role = "user" if msg.role == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

        contents.append(types.Content(role="user", parts=[types.Part(text=user_content)]))

        response = None
        last_error = None
        tried_models = []

        for model_name in fallback_models:
            try:
                print(f"Attempting to generate content with model: {model_name}")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                print(f"Successfully generated content with model: {model_name}")
                break
            except Exception as e:
                print(f"Warning: Model {model_name} failed: {e}")
                last_error = e
                tried_models.append(model_name)

        if response is None:
            raise HTTPException(
                status_code=500,
                detail=f"All attempted models ({', '.join(tried_models)}) failed. Last error: {str(last_error)}"
            )

        # Save user message to DB
        user_msg = DBMessage(
            id=request.message_id,
            session_id=request.session_id,
            role="user",
            content=request.message,
            timestamp=int(time.time() * 1000)
        )
        db.add(user_msg)

        # Save bot message to DB
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

        return {
            "id": bot_id,
            "reply": response.text,
            "sources": sources,
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
