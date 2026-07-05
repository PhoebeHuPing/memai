"""Session management routes."""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from server.database import get_session
from server.models import ChatMessage as DBMessage, ChatSession
from server.schemas import RenameSessionRequest

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_session)):
    """Return all session IDs with their last activity timestamp and title."""
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

    first_messages: dict[str, str] = {}
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


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: str, request: RenameSessionRequest, db: Session = Depends(get_session)
):
    """Rename a session. Creates a ChatSession record if it doesn't exist."""
    chat_session = db.get(ChatSession, session_id)
    if chat_session:
        chat_session.title = request.title
    else:
        msg = db.exec(select(DBMessage).where(DBMessage.session_id == session_id)).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Session not found")
        chat_session = ChatSession(
            id=session_id, title=request.title, created_at=int(time.time() * 1000)
        )
        db.add(chat_session)
    db.commit()
    return {"status": "ok", "session_id": session_id, "title": request.title}


@router.delete("/sessions/{session_id}")
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
