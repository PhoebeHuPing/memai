"""
Integration tests for RAG-based chat endpoint
Tests the complete flow from user query to RAG retrieval to Gemini response
"""
import os
import sys
import unittest
import tempfile
import json
from unittest.mock import patch, MagicMock, PropertyMock
from fastapi.testclient import TestClient
from sqlmodel import create_engine, SQLModel, Session, select

# Add project root to path
sys.path.append(os.getcwd())

# Set up test database before importing app
test_dir = tempfile.mkdtemp()
os.environ["TEST_DB_PATH"] = os.path.join(test_dir, "test_chat.db")


class TestRAGChatIntegration(unittest.TestCase):
    """Test RAG-based chat endpoint integration"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test client, database, and RAG service"""
        # Set up test database
        from server import database
        from server.models import SQLModel as BaseModel
        
        cls.test_db_path = os.path.join(test_dir, "test_rag_chat.db")
        cls.sqlite_url = f"sqlite:///{cls.test_db_path}"
        cls.engine = create_engine(cls.sqlite_url, echo=False)
        
        # Create tables
        BaseModel.metadata.create_all(cls.engine)
        
        # Patch the database module
        database.engine = cls.engine
        
        # Patch get_session
        def override_get_session():
            with Session(cls.engine) as session:
                yield session
        
        # Mock RAG service with sample data
        cls.mock_rag_service = MagicMock()
        cls.mock_rag_service.chroma_collection.count.return_value = 3
        cls.mock_rag_service.query.return_value = {
            "context": """
Page 1 of Ministry of Education Handbook: Property Management
The Five-Year Agreement (5YA) outlines the key properties...

Page 2 of Policy Guide: MOE Priority Levels
Priority 1 (Urgent): Safety hazards that require immediate attention.
Priority 2 (High): Significant issues affecting functionality.
Priority 3 (Medium): Maintenance that should be scheduled soon.
Priority 4 (Low): Minor issues for routine maintenance.
            """,
            "sources": [
                {"file": "MOE-Property-Handbook.pdf", "page": "1", "score": 0.92},
                {"file": "Policy-Guide.pdf", "page": "2", "score": 0.88},
            ]
        }
        
        # Import and patch main app
        from server.main import app
        app.dependency_overrides[database.get_session] = override_get_session
        
        # Patch RAG service
        import server.main
        server.main.rag_service = cls.mock_rag_service
        
        # Mock Gemini client
        cls.mock_client = MagicMock()
        cls.mock_response = MagicMock()
        cls.mock_response.text = "Based on MOE policy, this falls under Priority 2 (High). The 5YA framework typically requires..."
        cls.mock_client.models.generate_content.return_value = cls.mock_response
        server.main.client = cls.mock_client
        
        cls.client = TestClient(app)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up"""
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
    
    def setUp(self):
        """Clear database before each test"""
        from server.models import ChatMessage
        with Session(self.engine) as session:
            messages = session.exec(select(ChatMessage)).all()
            for msg in messages:
                session.delete(msg)
            session.commit()
    
    def test_chat_with_rag_context(self):
        """Test that chat endpoint injects RAG context into prompt"""
        response = self.client.post(
            "/api/v1/chat",
            json={
                "message_id": "msg-001",
                "message": "What is the MOE priority level for a structural hazard?",
                "history": [],
                "session_id": "test-session",
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertIn("id", data)
        self.assertIn("reply", data)
        self.assertIn("sources", data)
        
        # Verify sources are returned
        self.assertEqual(len(data["sources"]), 2)
        self.assertEqual(data["sources"][0]["file"], "MOE-Property-Handbook.pdf")
    
    def test_chat_persists_to_database(self):
        """Test that user and assistant messages are saved to database"""
        from server.models import ChatMessage
        
        response = self.client.post(
            "/api/v1/chat",
            json={
                "message_id": "msg-002",
                "message": "Tell me about the 5YA framework",
                "history": [],
                "session_id": "test-session-2",
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Retrieve messages from database
        with Session(self.engine) as session:
            messages = session.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == "test-session-2")
                .order_by(ChatMessage.timestamp)
            ).all()
            
            # Should have user message and assistant message
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0].role, "user")
            self.assertEqual(messages[0].content, "Tell me about the 5YA framework")
            self.assertEqual(messages[1].role, "assistant")
            self.assertIsNotNone(messages[1].sources)
    
    def test_chat_without_rag_documents(self):
        """Test chat fallback when RAG has no documents"""
        # Mock RAG service with no documents
        self.mock_rag_service.chroma_collection.count.return_value = 0
        
        response = self.client.post(
            "/api/v1/chat",
            json={
                "message_id": "msg-003",
                "message": "What policies exist?",
                "history": [],
                "session_id": "test-session-3",
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should still get response but no sources
        self.assertIn("reply", data)
        # No RAG context injected means no sources
        self.assertEqual(data["sources"], [])
        
        # Restore RAG service
        self.mock_rag_service.chroma_collection.count.return_value = 3
    
    def test_chat_with_conversation_history(self):
        """Test that conversation history is included in context"""
        response = self.client.post(
            "/api/v1/chat",
            json={
                "message_id": "msg-004",
                "message": "What should we do about it?",
                "history": [
                    {"role": "user", "content": "We have a roof leak"},
                    {"role": "assistant", "content": "That's a Priority 1 issue"},
                ],
                "session_id": "test-session-4",
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the Gemini client received the history
        call_args = self.mock_client.models.generate_content.call_args
        self.assertIsNotNone(call_args)
        # Check that contents list includes the history
        contents = call_args[1]["contents"]
        self.assertTrue(len(contents) >= 3)  # system, history, + new message
    
    def test_sources_metadata_preserved(self):
        """Test that source metadata is correctly preserved in database"""
        from server.models import ChatMessage
        
        response = self.client.post(
            "/api/v1/chat",
            json={
                "message_id": "msg-005",
                "message": "What are the priority levels?",
                "history": [],
                "session_id": "test-session-5",
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Get assistant message from database
        with Session(self.engine) as session:
            bot_msg = session.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == "test-session-5")
                .where(ChatMessage.role == "assistant")
            ).first()
            
            self.assertIsNotNone(bot_msg)
            sources = json.loads(bot_msg.sources)
            
            # Verify all source metadata is preserved
            self.assertEqual(len(sources), 2)
            self.assertIn("file", sources[0])
            self.assertIn("page", sources[0])
            self.assertIn("score", sources[0])
            self.assertEqual(sources[0]["score"], 0.92)
    
    def test_multiple_sessions_isolated(self):
        """Test that different sessions don't interfere with each other"""
        from server.models import ChatMessage
        
        # Send messages in two sessions
        for session_id in ["session-a", "session-b"]:
            self.client.post(
                "/api/v1/chat",
                json={
                    "message_id": f"msg-{session_id}",
                    "message": f"Query from {session_id}",
                    "history": [],
                    "session_id": session_id,
                }
            )
        
        # Verify messages are isolated
        with Session(self.engine) as session:
            msgs_a = session.exec(
                select(ChatMessage).where(ChatMessage.session_id == "session-a")
            ).all()
            msgs_b = session.exec(
                select(ChatMessage).where(ChatMessage.session_id == "session-b")
            ).all()
            
            self.assertEqual(len(msgs_a), 2)  # user + assistant
            self.assertEqual(len(msgs_b), 2)  # user + assistant
            
            # Verify content is different
            self.assertNotIn("session-b", msgs_a[0].content)
            self.assertNotIn("session-a", msgs_b[0].content)


if __name__ == "__main__":
    unittest.main()
