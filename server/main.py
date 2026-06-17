import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
if not api_key:
    print("Warning: GOOGLE_GENERATIVE_AI_API_KEY not found")
    client = None
else:
    client = genai.Client(api_key=api_key)

# Initialize RAG service
from server.services.rag_service import RAGService
try:
    rag_service = RAGService()
    print(f"RAG service initialized. Collection has {rag_service.chroma_collection.count()} documents.")
except Exception as e:
    print(f"Warning: RAG service failed to initialize: {e}")
    rag_service = None

app = FastAPI()

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
    content: str
    timestamp: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    history: List[Message]


@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
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

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
        )

        return {
            "reply": response.text,
            "sources": sources,
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
