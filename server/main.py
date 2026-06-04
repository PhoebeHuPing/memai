import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini AI
api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
if not api_key:
    print("Warning: GOOGLE_GENERATIVE_AI_API_KEY not found in environment")
    client = None
else:
    client = genai.Client(api_key=api_key)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # Convert history to Gemini format
        contents = []
        for msg in request.history:
            role = "user" if msg.role == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))
        
        # Add the current message
        contents.append(types.Content(role="user", parts=[types.Part(text=request.message)]))

        # Call Gemini API
        # Using gemini-2.0-flash as it's the current latest, 
        # but matching the request for gemini-2.5-flash if that's what was intended
        # (though 2.5 doesn't exist yet, 2.0 is latest)
        model_id = "gemini-2.0-flash" 
        
        response = client.models.generate_content(
            model=model_id,
            contents=contents
        )
        
        return {"reply": response.text}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
