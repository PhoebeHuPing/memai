from sqlmodel import SQLModel, Field

class ChatMessage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    role: str
    content: str
    timestamp: int
