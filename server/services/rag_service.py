import os
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.gemini import GeminiEmbedding


class RAGService:
    def __init__(self, db_path: str = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.path.join(base_dir, "data", "chroma_db")
        self.collection_name = "nz_school_property_policy"

        os.makedirs(self.db_path, exist_ok=True)

        # Use Gemini embedding (free, uses existing GOOGLE_GENERATIVE_AI_API_KEY)
        api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
        Settings.embed_model = GeminiEmbedding(
            api_key=api_key,
            model_name="models/gemini-embedding-001",
        )

        self.client = chromadb.PersistentClient(path=self.db_path)
        self.chroma_collection = self.client.get_or_create_collection(self.collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    def ingest_documents(self, data_dir: str):
        """Ingest PDF documents from a directory into ChromaDB."""
        from llama_index.core.schema import TextNode
        from pypdf import PdfReader
        import glob

        # Clear existing data to avoid duplicates
        self.client.delete_collection(self.collection_name)
        self.chroma_collection = self.client.create_collection(self.collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        # Parse PDFs manually with pypdf
        pdf_files = glob.glob(os.path.join(data_dir, "*.pdf"))
        nodes = []
        for pdf_path in pdf_files:
            reader = PdfReader(pdf_path)
            file_name = os.path.basename(pdf_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                    nodes.append(TextNode(
                        text=text,
                        metadata={"file_name": file_name, "page_label": str(i + 1)},
                    ))

        print(f"Loaded {len(nodes)} page chunks from {len(pdf_files)} PDF(s)")

        index = VectorStoreIndex(
            nodes,
            storage_context=self.storage_context,
            show_progress=True,
        )
        return index

    def query(self, question: str, top_k: int = 3) -> dict:
        """Retrieve relevant document chunks for a question."""
        index = VectorStoreIndex.from_vector_store(
            self.vector_store,
            storage_context=self.storage_context,
        )
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(question)

        sources = []
        context_texts = []
        for node in nodes:
            meta = node.metadata
            sources.append({
                "file": meta.get("file_name", "unknown"),
                "page": meta.get("page_label", "unknown"),
                "score": round(node.score, 3) if node.score else None,
            })
            context_texts.append(node.get_text())

        return {
            "context": "\n\n---\n\n".join(context_texts),
            "sources": sources,
        }
