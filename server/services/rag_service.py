import os
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import nest_asyncio

class RAGService:
    def __init__(self):
        # Patch: Early validation of API Keys (Fail Fast)
        self.llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not self.llama_api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY not found in environment variables. Please add it to your .env file.")

        # Patch: Safer path resolution relative to this file's directory
        # __file__ is server/services/rag_service.py, so two levels up is server/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, "data", "chroma_db")
        self.collection_name = "nz_school_property_policy"
        
        # Patch: Ensure persistence directory exists before initializing client
        os.makedirs(self.db_path, exist_ok=True)
        
        # Patch: Move nest_asyncio here to avoid global side-effects at module level
        nest_asyncio.apply()
        
        # Initialize ChromaDB PersistentClient
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.chroma_collection = self.client.get_or_create_collection(self.collection_name)
        
        # Set up Vector Store and Storage Context
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
    def ingest_documents(self, data_dir: str):
        """
        Ingests PDF documents from a directory using LlamaParse and stores them in ChromaDB.
        """
        try:
            # Decision Resolution: Simple Mode - Clear collection before re-ingestion
            # This prevents duplicate embeddings if the script is run multiple times.
            self.client.delete_collection(self.collection_name)
            self.chroma_collection = self.client.create_collection(self.collection_name)
            
            # Re-initialize vector store and storage context for the new collection
            self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
            self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

            # Configure LlamaParse for high-fidelity Markdown extraction
            parser = LlamaParse(
                api_key=self.llama_api_key,
                result_type="markdown",
                verbose=True
            )
            
            file_extractor = {".pdf": parser}
            
            # Load data using SimpleDirectoryReader with LlamaParse extractor
            reader = SimpleDirectoryReader(
                input_dir=data_dir,
                file_extractor=file_extractor
            )
            
            documents = reader.load_data()
            
            # Build index and persist to ChromaDB
            index = VectorStoreIndex.from_documents(
                documents, 
                storage_context=self.storage_context,
                show_progress=True
            )
            
            return index
        except Exception as e:
            # Patch: Added basic exception handling for network/IO errors
            print(f"Error during document ingestion: {e}")
            raise e

    def get_index(self):
        """
        Loads the existing index from the vector store.
        """
        return VectorStoreIndex.from_vector_store(
            self.vector_store,
            storage_context=self.storage_context
        )
