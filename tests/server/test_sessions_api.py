"""
Integration tests for sessions API endpoints (list, rename, delete).
"""
import os
import sys
import time
import unittest
import tempfile

from fastapi.testclient import TestClient
from sqlmodel import create_engine, SQLModel, Session, select

# Add project root to path
sys.path.append(os.getcwd())

# Set up test database before importing app
test_dir = tempfile.mkdtemp()
os.environ["TEST_DB_PATH"] = os.path.join(test_dir, "test_sessions.db")


class TestSessionsAPI(unittest.TestCase):
    """Test sessions management endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up test client and database."""
        from server import database
        from server.models import SQLModel as BaseModel

        cls.test_db_path = os.path.join(test_dir, "test_sessions.db")
        cls.sqlite_url = f"sqlite:///{cls.test_db_path}"
        cls.engine = create_engine(cls.sqlite_url, echo=False)

        # Create tables
        BaseModel.metadata.create_all(cls.engine)

        # Patch the database module
        database.engine = cls.engine

        def override_get_session():
            with Session(cls.engine) as session:
                yield session

        from server.main import app

        app.dependency_overrides[database.get_session] = override_get_session

        cls.client = TestClient(app)

    def setUp(self):
        """Clear database before each test."""
        from server.models import ChatMessage, ChatSession

        with Session(self.engine) as session:
            messages = session.exec(select(ChatMessage)).all()
            for msg in messages:
                session.delete(msg)
            sessions = session.exec(select(ChatSession)).all()
            for s in sessions:
                session.delete(s)
            session.commit()

    # ─── Helpers ───────────────────────────────────────────────

    def _add_message(self, session_id: str, role: str, content: str, timestamp: int):
        """Insert a message directly into the database."""
        from server.models import ChatMessage
        import uuid

        msg = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            timestamp=timestamp,
        )
        with Session(self.engine) as db:
            db.add(msg)
            db.commit()

    def _add_session(self, session_id: str, title: str):
        """Insert a ChatSession record directly into the database."""
        from server.models import ChatSession

        cs = ChatSession(id=session_id, title=title, created_at=int(time.time() * 1000))
        with Session(self.engine) as db:
            db.add(cs)
            db.commit()

    # ─── GET /api/v1/sessions ──────────────────────────────────

    def test_list_sessions_empty(self):
        """Returns empty list when no messages exist."""
        response = self.client.get("/api/v1/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_sessions_returns_sessions_ordered_by_last_active(self):
        """Sessions are ordered by last_active descending."""
        self._add_message("session-old", "user", "Hello old", 1000)
        self._add_message("session-new", "user", "Hello new", 2000)

        response = self.client.get("/api/v1/sessions")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["session_id"], "session-new")
        self.assertEqual(data[1]["session_id"], "session-old")

    def test_list_sessions_uses_custom_title(self):
        """If a ChatSession with a title exists, use it."""
        self._add_session("s1", "My Custom Title")
        self._add_message("s1", "user", "First message", 1000)

        response = self.client.get("/api/v1/sessions")
        data = response.json()
        self.assertEqual(data[0]["title"], "My Custom Title")

    def test_list_sessions_falls_back_to_first_user_message(self):
        """Without a ChatSession title, fallback to first user message (truncated to 40 chars)."""
        self._add_message("s2", "user", "A short question", 1000)

        response = self.client.get("/api/v1/sessions")
        data = response.json()
        self.assertEqual(data[0]["title"], "A short question")

    def test_list_sessions_truncates_long_fallback_title(self):
        """Fallback title is truncated at 40 characters."""
        long_msg = "A" * 60
        self._add_message("s3", "user", long_msg, 1000)

        response = self.client.get("/api/v1/sessions")
        data = response.json()
        self.assertEqual(len(data[0]["title"]), 40)

    def test_list_sessions_includes_last_active_timestamp(self):
        """Each session includes its last_active timestamp."""
        self._add_message("s4", "user", "msg1", 1000)
        self._add_message("s4", "assistant", "reply", 2000)

        response = self.client.get("/api/v1/sessions")
        data = response.json()
        self.assertEqual(data[0]["last_active"], 2000)

    # ─── PATCH /api/v1/sessions/{session_id} ───────────────────

    def test_rename_session_creates_record_if_not_exists(self):
        """Renaming a session that has messages but no ChatSession record creates one."""
        self._add_message("s5", "user", "hello", 1000)

        response = self.client.patch(
            "/api/v1/sessions/s5", json={"title": "New Title"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "New Title")

        # Verify title persists in list
        sessions = self.client.get("/api/v1/sessions").json()
        self.assertEqual(sessions[0]["title"], "New Title")

    def test_rename_session_updates_existing_record(self):
        """Renaming a session with an existing ChatSession record updates the title."""
        self._add_session("s6", "Old Title")
        self._add_message("s6", "user", "hello", 1000)

        response = self.client.patch(
            "/api/v1/sessions/s6", json={"title": "Updated Title"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Updated Title")

    def test_rename_session_not_found(self):
        """Renaming a session with no messages returns 404."""
        response = self.client.patch(
            "/api/v1/sessions/nonexistent", json={"title": "Nope"}
        )
        self.assertEqual(response.status_code, 404)

    def test_rename_session_empty_title_rejected(self):
        """Empty title is rejected by validation (min_length=1)."""
        self._add_message("s7", "user", "hello", 1000)

        response = self.client.patch(
            "/api/v1/sessions/s7", json={"title": ""}
        )
        self.assertEqual(response.status_code, 422)

    def test_rename_session_too_long_title_rejected(self):
        """Title exceeding 60 characters is rejected."""
        self._add_message("s8", "user", "hello", 1000)

        response = self.client.patch(
            "/api/v1/sessions/s8", json={"title": "X" * 61}
        )
        self.assertEqual(response.status_code, 422)

    # ─── DELETE /api/v1/sessions/{session_id} ──────────────────

    def test_delete_session_removes_messages_and_record(self):
        """Deleting a session removes all messages and the ChatSession record."""
        self._add_session("s9", "To Delete")
        self._add_message("s9", "user", "msg1", 1000)
        self._add_message("s9", "assistant", "reply1", 2000)

        response = self.client.delete("/api/v1/sessions/s9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

        # Verify session no longer appears in list
        sessions = self.client.get("/api/v1/sessions").json()
        session_ids = [s["session_id"] for s in sessions]
        self.assertNotIn("s9", session_ids)

    def test_delete_session_not_found(self):
        """Deleting a session with no messages returns 404."""
        response = self.client.delete("/api/v1/sessions/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_delete_session_does_not_affect_other_sessions(self):
        """Deleting one session leaves other sessions intact."""
        self._add_message("keep-me", "user", "stay", 1000)
        self._add_message("delete-me", "user", "go", 2000)

        self.client.delete("/api/v1/sessions/delete-me")

        sessions = self.client.get("/api/v1/sessions").json()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "keep-me")


if __name__ == "__main__":
    unittest.main()
