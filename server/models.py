from sqlmodel import SQLModel, Field
from typing import Optional

class ChatSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: Optional[str] = Field(default=None)
    created_at: int = Field(default=0)

class ChatMessage(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str = Field(default="default", index=True)
    role: str
    content: str
    timestamp: int
    sources: Optional[str] = Field(default=None)
