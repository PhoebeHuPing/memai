import os
import glob
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.schema import TextNode
from pypdf import PdfReader


class RAGService:
    """Service wrapping a ChromaDB vector store for Retrieval‑Augmented Generation.

    - Documents are ingested from a directory of PDF files.
    - Gemini embeddings are used (free, requires GOOGLE_GENERATIVE_AI_API_KEY).
    - Provides ``query`` method returning ``context`` string and ``sources`` list.
    """

    def __init__(self, db_path: str | None = None):
        # Resolve a stable base directory two levels up (project root)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.path.join(base_dir, "data", "chroma_db")
        self.collection_name = "nz_school_policy"

        os.makedirs(self.db_path, exist_ok=True)

        # Initialise Gemini embedding model (requires API key)
        api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GOOGLE_GENERATIVE_AI_API_KEY for RAGService")
        Settings.embed_model = GeminiEmbedding(
            api_key=api_key,
            model_name="models/gemini-embedding-001",
        )

        # Persistent Chroma client & collection
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.chroma_collection = self.client.get_or_create_collection(self.collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    # ---------------------------------------------------------------------
    # Ingestion
    # ---------------------------------------------------------------------
    def ingest_documents(self, data_dir: str) -> VectorStoreIndex:
        """Load all PDFs under *data_dir* into the Chroma collection.

        Existing collection is cleared to avoid duplicate chunks.
        Returns the created ``VectorStoreIndex`` for optional further use.
        """
        # Reset collection to avoid stale data
        self.client.delete_collection(self.collection_name)
        self.chroma_collection = self.client.create_collection(self.collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        pdf_files = glob.glob(os.path.join(data_dir, "*.pdf"))
        nodes: list[TextNode] = []

        for pdf_path in pdf_files:
            reader = PdfReader(pdf_path)
            file_name = os.path.basename(pdf_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    nodes.append(
                        TextNode(
                            text=text,
                            metadata={"file_name": file_name, "page_label": str(i + 1)},
                        )
                    )

        print(f"Loaded {len(nodes)} page chunks from {len(pdf_files)} PDF(s)")

        index = VectorStoreIndex(
            nodes,
            storage_context=self.storage_context,
            show_progress=True,
        )
        return index

    # ---------------------------------------------------------------------
    # Query
    # ---------------------------------------------------------------------
    def query(self, question: str, top_k: int = 3) -> dict:
        """Retrieve the most relevant document chunks for *question*.

        Returns a dict with two keys:
        - ``context``: concatenated chunk texts separated by ``---``.
        - ``sources``: list of metadata dicts (file, page, score).
        """
        try:
            index = VectorStoreIndex.from_vector_store(
                self.vector_store, storage_context=self.storage_context
            )
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(question)

            sources = []
            context_texts = []
            for node in nodes:
                meta = node.metadata
                sources.append(
                    {
                        "file": meta.get("file_name", "unknown"),
                        "page": meta.get("page_label", "unknown"),
                        "score": round(node.score, 3) if getattr(node, "score", None) else None,
                    }
                )
                context_texts.append(node.get_text())

            return {"context": "\n\n---\n\n".join(context_texts), "sources": sources}
        except Exception as exc:
            # Log error and return empty result to keep API functional
            print(f"[RAGService] query error: {exc}")
            return {"context": "", "sources": []}
