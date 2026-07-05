"""Pydantic request/response schemas for the API."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    id: Optional[str] = None
    role: str
    content: str = Field(max_length=50000)
    timestamp: Optional[int] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v


class ChatRequest(BaseModel):
    message_id: str = Field(max_length=100)
    message: str = Field(min_length=1, max_length=10000)
    history: List[Message] = Field(default=[], max_length=100)
    session_id: str = Field(
        default="default", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$"
    )


class RenameSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)


class ErrorResponse(BaseModel):
    """Unified error response returned to the frontend."""

    error_code: str
    message: str
    detail: Optional[str] = None
