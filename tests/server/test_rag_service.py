import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

# Mock environment variable before importing RAGService if possible, 
# but RAGService checks os.getenv in __init__.
os.environ["LLAMA_CLOUD_API_KEY"] = "test_key"

from server.services.rag_service import RAGService

class TestRAGService(unittest.TestCase):
    def setUp(self):
        # Use a temporary path for chroma_db during testing
        self.test_db_path = os.path.join(os.getcwd(), "server", "data", "test_chroma_db")
        if not os.path.exists(self.test_db_path):
            os.makedirs(self.test_db_path)
            
    @patch('chromadb.PersistentClient')
    def test_initialization(self, mock_chroma):
        # Mocking ChromaDB to avoid actual filesystem usage in this test
        service = RAGService()
        self.assertIsNotNone(service.client)
        self.assertEqual(service.collection_name, "nz_school_property_policy")

    @patch('server.services.rag_service.LlamaParse')
    @patch('server.services.rag_service.SimpleDirectoryReader')
    @patch('server.services.rag_service.VectorStoreIndex')
    def test_ingestion_fails_without_api_key(self, mock_index, mock_reader, mock_parse):
        # Temporarily remove key to test Fail Fast in __init__
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                RAGService()

if __name__ == "__main__":
    unittest.main()
