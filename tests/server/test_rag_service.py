import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

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
        # Ensure LLAMA_CLOUD_API_KEY is NOT set
        if "LLAMA_CLOUD_API_KEY" in os.environ:
            del os.environ["LLAMA_CLOUD_API_KEY"]
            
        service = RAGService()
        with self.assertRaises(ValueError):
            service.ingest_documents("some_dir")

if __name__ == "__main__":
    unittest.main()
