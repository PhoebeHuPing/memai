"""
Integration tests for SQLite database persistence with ChatMessage model
"""
import os
import sys
import unittest
import tempfile
from sqlmodel import create_engine, Session, select

# Add project root to path
sys.path.append(os.getcwd())

from server.models import ChatMessage
from server.database import get_session


class TestDatabaseIntegration(unittest.TestCase):
    """Test SQLite database creation and CRUD operations"""
    
    @classmethod
    def setUpClass(cls):
        """Create a temporary database for testing"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db_path = os.path.join(cls.temp_dir, "test_chat.db")
        cls.sqlite_url = f"sqlite:///{cls.temp_dir}/test_chat.db"
        
        # Create test engine
        cls.engine = create_engine(cls.sqlite_url, echo=False)
        
        # Create tables
        from server.models import SQLModel as BaseModel
        BaseModel.metadata.create_all(cls.engine)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary database"""
        import shutil
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
    
    def setUp(self):
        """Clear database before each test"""
        with Session(self.engine) as session:
            # Clear all messages
            messages = session.exec(select(ChatMessage)).all()
            for msg in messages:
                session.delete(msg)
            session.commit()
    
    def test_create_message(self):
        """Test creating a chat message in database"""
        msg = ChatMessage(
            id="msg-001",
            session_id="default",
            role="user",
            content="Hello, MemAI!",
            timestamp=1234567890000,
        )
        
        with Session(self.engine) as session:
            session.add(msg)
            session.commit()
            session.refresh(msg)
            self.assertEqual(msg.id, "msg-001")
    
    def test_retrieve_messages_by_session(self):
        """Test retrieving messages filtered by session_id"""
        # Create messages in two sessions
        messages_data = [
            ("msg-1", "session-a", "user", "Question 1", 1000),
            ("msg-2", "session-a", "assistant", "Answer 1", 2000),
            ("msg-3", "session-b", "user", "Question 2", 3000),
        ]
        
        with Session(self.engine) as session:
            for msg_id, session_id, role, content, timestamp in messages_data:
                msg = ChatMessage(
                    id=msg_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    timestamp=timestamp,
                )
                session.add(msg)
            session.commit()
        
        # Retrieve messages for session-a
        with Session(self.engine) as session:
            session_a_msgs = session.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == "session-a")
                .order_by(ChatMessage.timestamp)
            ).all()
            
            self.assertEqual(len(session_a_msgs), 2)
            self.assertEqual(session_a_msgs[0].id, "msg-1")
            self.assertEqual(session_a_msgs[1].id, "msg-2")
    
    def test_delete_messages_by_session(self):
        """Test deleting all messages for a session"""
        messages_data = [
            ("msg-1", "session-a", "user", "Q1", 1000),
            ("msg-2", "session-a", "assistant", "A1", 2000),
            ("msg-3", "session-b", "user", "Q2", 3000),
        ]
        
        with Session(self.engine) as session:
            for msg_id, session_id, role, content, timestamp in messages_data:
                msg = ChatMessage(
                    id=msg_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    timestamp=timestamp,
                )
                session.add(msg)
            session.commit()
        
        # Delete session-a messages
        with Session(self.engine) as session:
            to_delete = session.exec(
                select(ChatMessage).where(ChatMessage.session_id == "session-a")
            ).all()
            for msg in to_delete:
                session.delete(msg)
            session.commit()
        
        # Verify deletion
        with Session(self.engine) as session:
            remaining = session.exec(select(ChatMessage)).all()
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].session_id, "session-b")
    
    def test_message_with_sources(self):
        """Test storing message with JSON sources"""
        import json
        sources = json.dumps([
            {"file": "policy.pdf", "page": "1", "score": 0.95},
            {"file": "guide.pdf", "page": "5", "score": 0.87},
        ])
        
        msg = ChatMessage(
            id="msg-with-sources",
            session_id="default",
            role="assistant",
            content="Based on the policies...",
            timestamp=1234567890000,
            sources=sources,
        )
        
        with Session(self.engine) as session:
            session.add(msg)
            session.commit()
            session.refresh(msg)
            
            retrieved = session.exec(
                select(ChatMessage).where(ChatMessage.id == "msg-with-sources")
            ).first()
            
            self.assertIsNotNone(retrieved.sources)
            parsed_sources = json.loads(retrieved.sources)
            self.assertEqual(len(parsed_sources), 2)
            self.assertEqual(parsed_sources[0]["file"], "policy.pdf")


if __name__ == "__main__":
    unittest.main()
