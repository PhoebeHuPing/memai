# Adding RAG to My AI Chatbot: Turning a Parrot into an Oracle

> How I upgraded a basic chatbot from "vibes-based answers" to a knowledge-grounded assistant that actually knows what it's talking about.

---

## The Problem: My Chatbot Was Confidently Wrong

I built MemAI — a full-stack chatbot powered by Google's Gemini 2.0 Flash. It could hold a conversation, it was fast, it sounded smart. But here's the thing: it was essentially a well-spoken parrot. Ask it about specific NZ school property policy? It'd hallucinate regulations that don't exist. Cite handbooks it never read. Invent acronyms with alarming creativity.

The gap between "can chat" and "actually useful" turned out to be enormous. I needed my bot to answer questions grounded in *real documents* — Ministry of Education handbooks, policy PDFs, the kind of dense bureaucratic material no human wants to re-read five times.

Enter **RAG** — Retrieval-Augmented Generation.

---

## What RAG Actually Is (No Buzzword Soup)

RAG is dead simple in concept:

1. **Retrieve** — find the most relevant chunks from your knowledge base
2. **Augment** — inject those chunks into the LLM's prompt as context
3. **Generate** — let the model answer *based on what it just read*, not what it vaguely remembers from training

Think of it as giving the AI an open-book exam instead of relying on its memory. The result: grounded answers with actual citations.

---

## My Stack Choices (and Why)

| Layer | Tool | Reasoning |
|-------|------|-----------|
| Vector DB | **ChromaDB** | Local, zero-config, PersistentClient means data survives restarts |
| PDF Parsing | **LlamaParse** | High-fidelity Markdown extraction — preserves tables, headers, structure |
| Orchestration | **LlamaIndex** | Handles chunking, embedding, retrieval pipeline out of the box |
| LLM | **Gemini 2.0 Flash** | Already integrated, fast enough for real-time chat |

I deliberately avoided cloud-hosted vector databases. For a bootcamp project processing a handful of PDFs, ChromaDB's local persistence was perfect — no infrastructure overhead, no API costs for storage.

---

## The Implementation: Three Moving Parts

### Part 1: The RAG Service

Everything lives in `server/services/rag_service.py`. The architectural rule was strict: **all AI logic stays in `server/services/`**. No LLM calls scattered across route handlers.

```python
class RAGService:
    def __init__(self):
        self.llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not self.llama_api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY not found")

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, "data", "chroma_db")
        os.makedirs(self.db_path, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.db_path)
        self.chroma_collection = self.client.get_or_create_collection(
            "nz_school_property_policy"
        )
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
```

Key decisions here:

- **Fail-fast on missing keys.** If `LLAMA_CLOUD_API_KEY` isn't set, crash immediately with a clear message. Don't let it silently fail three layers deep.
- **Relative path resolution.** `os.path.dirname(__file__)` instead of hardcoded paths. Future me will thank past me when the project moves directories.
- **`get_or_create_collection`** — idempotent initialization. Run it ten times, get the same result.

### Part 2: Document Ingestion

The ingestion script (`server/scripts/ingest_docs.py`) is a one-shot pipeline: drop PDFs in `server/data/`, run the script, get a populated vector store.

```python
def ingest_documents(self, data_dir: str):
    # Nuke and rebuild — prevents duplicate embeddings
    self.client.delete_collection(self.collection_name)
    self.chroma_collection = self.client.create_collection(self.collection_name)

    parser = LlamaParse(
        api_key=self.llama_api_key,
        result_type="markdown",
        verbose=True
    )

    reader = SimpleDirectoryReader(
        input_dir=data_dir,
        file_extractor={".pdf": parser}
    )

    documents = reader.load_data()

    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=self.storage_context,
        show_progress=True
    )
    return index
```

The controversial choice: **delete-then-recreate** the collection on every ingestion run. This is intentional for an MVP. With a handful of policy documents, re-ingesting from scratch takes seconds. No deduplication logic, no diffing, no complexity. When the document count grows, I'd switch to incremental upserts — but that's a Phase 3 problem.

### Part 3: The Query Path

Once the vector store is populated, querying is almost anticlimactic:

```python
def get_index(self):
    return VectorStoreIndex.from_vector_store(
        self.vector_store,
        storage_context=self.storage_context
    )
```

LlamaIndex handles the heavy lifting — embedding the user's query, performing similarity search against ChromaDB, returning the top-k chunks, and feeding them into the LLM's context window.

---

## The Gotchas (A.K.A. Things That Broke)

### 1. `nest_asyncio` — The Async Event Loop Conflict

LlamaParse uses async internally. FastAPI also runs an async event loop. Running LlamaParse inside a FastAPI context? Instant `RuntimeError: This event loop is already running`.

The fix is ugly but effective:

```python
import nest_asyncio
nest_asyncio.apply()
```

This patches the running event loop to allow nested async calls. It's a well-known workaround in the Jupyter/FastAPI/LlamaIndex ecosystem. Not elegant, but it works.

### 2. Path Resolution Across Execution Contexts

When you run `python server/scripts/ingest_docs.py` from the project root vs. running it from `server/scripts/`, all relative paths break. The solution:

```python
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

Anchor everything to the file's actual location on disk, then navigate relatively from there.

### 3. ChromaDB's Silent Collection Duplication

If you call `ingest_documents()` twice without clearing the collection, you get duplicate embeddings. Same document, embedded twice, polluting your retrieval results. The "delete and rebuild" approach eliminates this entirely for development.

---

## What I Actually Learned

**RAG is 80% plumbing, 20% AI.** The "magic" part — the LLM generating answers — was already working. The real engineering challenge was:

- Getting PDFs parsed without losing table structure
- Managing vector store lifecycle (creation, persistence, cleanup)
- Handling path resolution across different execution contexts
- Designing for idempotent operations (run it twice, same result)

**The quality of your retrieval determines everything.** If LlamaParse mangles a table, the LLM gets garbage context, and produces garbage answers. "Garbage in, garbage out" is brutally literal with RAG.

**Start simple, iterate.** My first instinct was to build sophisticated chunking strategies, overlap windows, metadata filtering. Instead, I used LlamaIndex's defaults, got a working system in hours, and now have a baseline to improve against.

---

## The Before and After

**Before RAG:**
> User: "What's the 5YA funding process for roof repairs?"
> Bot: "The 5YA funding process typically involves submitting a maintenance request to your regional education office..." *(completely fabricated)*

**After RAG:**
> User: "What's the 5YA funding process for roof repairs?"
> Bot: "According to the MOE Property Management Handbook (Section 4.2), 5YA funding for roof repairs requires..." *(cites actual document, actual section)*

That's the difference between a toy and a tool.

---

## What's Next

- **Citation UI** — display source references inline so users can verify
- **Streaming responses** — chunk-by-chunk delivery for better perceived latency
- **Multi-modal** — combine image analysis of property damage with policy retrieval
- **Incremental ingestion** — update the knowledge base without full rebuilds

---

## TL;DR

Adding RAG to a chatbot is less about AI wizardry and more about solid data engineering. Parse your documents well, store embeddings reliably, retrieve accurately, and let the LLM do what it's good at — generating coherent text from good context.

The bar for "useful AI application" is higher than "it can chat." RAG is how you clear it.

---

*Stack: FastAPI + ChromaDB + LlamaIndex + LlamaParse + Gemini 2.0 Flash.*
