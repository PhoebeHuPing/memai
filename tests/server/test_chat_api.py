"""
Integration tests for FastAPI chat endpoints with SQLite database
"""
import os
import sys
import unittest
import tempfile
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlmodel import create_engine, SQLModel, Session

# Add project root to path
sys.path.append(os.getcwd())

# Set up test database before importing app
test_dir = tempfile.mkdtemp()
os.environ["TEST_DB_PATH"] = os.path.join(test_dir, "test_chat.db")


class TestChatAPI(unittest.TestCase):
    """Test FastAPI chat endpoints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test client and database"""
        # We need to patch the database module before importing main
        from server import database
        from server.models import SQLModel as BaseModel
        
        cls.test_db_path = os.path.join(test_dir, "test_chat.db")
        cls.sqlite_url = f"sqlite:///{cls.test_db_path}"
        cls.engine = create_engine(cls.sqlite_url, echo=False)
        
        # Create tables FIRST
        BaseModel.metadata.create_all(cls.engine)
        
        # Patch the database module
        database.engine = cls.engine
        
        # Patch get_session
        def override_get_session():
            with Session(cls.engine) as session:
                yield session
        
        from server.main import app
        app.dependency_overrides[database.get_session] = override_get_session
        
        cls.client = TestClient(app)
    
    def setUp(self):
        """Clear database before each test"""
        from server.models import ChatMessage
        from sqlmodel import select
        
        with Session(self.engine) as session:
            messages = session.exec(select(ChatMessage)).all()
            for msg in messages:
                session.delete(msg)
            session.commit()
    
    def test_get_messages_empty(self):
        """Test getting messages from empty database"""
        response = self.client.get("/api/v1/messages?session_id=default")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
    
    def test_delete_messages_empty(self):
        """Test deleting messages from empty database"""
        response = self.client.delete("/api/v1/messages?session_id=default")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
    
    def test_get_messages_multiple_sessions(self):
        """Test that messages are isolated by session_id"""
        from server.models import ChatMessage
        
        # Add messages to two different sessions
        with Session(self.engine) as session:
            msg1 = ChatMessage(
                id="msg-1",
                session_id="session-a",
                role="user",
                content="Hello from A",
                timestamp=1000,
            )
            msg2 = ChatMessage(
                id="msg-2",
                session_id="session-b",
                role="user",
                content="Hello from B",
                timestamp=2000,
            )
            session.add(msg1)
            session.add(msg2)
            session.commit()
        
        # Get messages from session-a
        response = self.client.get("/api/v1/messages?session_id=session-a")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "msg-1")
        self.assertEqual(data[0]["content"], "Hello from A")
    
    def test_delete_messages_by_session(self):
        """Test deleting messages from specific session"""
        from server.models import ChatMessage
        
        # Add messages to two sessions
        with Session(self.engine) as session:
            msg1 = ChatMessage(
                id="msg-1",
                session_id="session-a",
                role="user",
                content="Hello from A",
                timestamp=1000,
            )
            msg2 = ChatMessage(
                id="msg-2",
                session_id="session-b",
                role="user",
                content="Hello from B",
                timestamp=2000,
            )
            session.add(msg1)
            session.add(msg2)
            session.commit()
        
        # Delete session-a messages
        response = self.client.delete("/api/v1/messages?session_id=session-a")
        self.assertEqual(response.status_code, 200)
        
        # Verify session-a is cleared but session-b remains
        response_a = self.client.get("/api/v1/messages?session_id=session-a")
        response_b = self.client.get("/api/v1/messages?session_id=session-b")
        
        self.assertEqual(len(response_a.json()), 0)
        self.assertEqual(len(response_b.json()), 1)
        self.assertEqual(response_b.json()[0]["content"], "Hello from B")
    
    def test_get_messages_with_sources(self):
        """Test retrieving messages with JSON sources"""
        from server.models import ChatMessage
        
        sources = json.dumps([
            {"file": "policy.pdf", "page": "1", "score": 0.95}
        ])
        
        with Session(self.engine) as session:
            msg = ChatMessage(
                id="msg-with-sources",
                session_id="default",
                role="assistant",
                content="Response with sources",
                timestamp=1000,
                sources=sources,
            )
            session.add(msg)
            session.commit()
        
        response = self.client.get("/api/v1/messages?session_id=default")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "msg-with-sources")
        # Sources should be in the response
        self.assertIn("sources", data[0])

    def test_chat_creates_session_title_from_first_message(self):
        """A new session should get a readable title based on the first user message."""
        from server.models import ChatSession
        from server.services import gemini_service

        with patch.object(gemini_service, "client", object()), patch(
            "server.routers.chat.generate_with_retry_and_fallback",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(text="Answer"),
        ), patch("server.routers.chat.rag_service", None):
            response = self.client.post(
                "/api/v1/chat",
                json={
                    "message_id": "msg-new-session",
                    "message": "What is the 5YA process?",
                    "history": [],
                    "session_id": "new-session",
                },
            )

        self.assertEqual(response.status_code, 200)
        with Session(self.engine) as session:
            chat_session = session.get(ChatSession, "new-session")
            self.assertIsNotNone(chat_session)
            self.assertEqual(chat_session.title, "What is the 5YA process")


if __name__ == "__main__":
    unittest.main()
