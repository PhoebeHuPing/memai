import os
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import nest_asyncio

# Required for async operations in certain environments
nest_asyncio.apply()

class RAGService:
    def __init__(self):
        # Local persistence path
        self.db_path = os.path.join(os.getcwd(), "server", "data", "chroma_db")
        self.collection_name = "nz_school_property_policy"
        
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
        api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY not found in environment variables. Please add it to your .env file.")
            
        # Configure LlamaParse for high-fidelity Markdown extraction (optimal for tables)
        parser = LlamaParse(
            api_key=api_key,
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

    def get_index(self):
        """
        Loads the existing index from the vector store.
        """
        return VectorStoreIndex.from_vector_store(
            self.vector_store,
            storage_context=self.storage_context
        )
