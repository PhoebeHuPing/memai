# MemAI: MOE Policy Chat Assistant

MemAI is a full-stack Retrieval-Augmented Generation (RAG) chatbot for answering questions about New Zealand school property management policy documents. It combines a React/TypeScript chat interface with a FastAPI backend, Google Gemini models, SQLite chat persistence, and a local ChromaDB vector store.

The current application is optimized for Ministry of Education (MOE) property-management questions. It retrieves relevant PDF context, asks Gemini to answer from that context, and returns source metadata so users can verify where an answer came from.

## Features

- **Policy-grounded chat**: Answers are generated with retrieved context from ingested MOE policy PDFs.
- **Source references**: Assistant responses can include document names, page numbers, and retrieval scores.
- **Persistent chat history**: Messages are stored in SQLite through SQLModel and reloaded on app start.
- **Session-aware API**: Backend endpoints support a `session_id`, so message histories can be isolated.
- **Gemini model fallback**: The backend tries the configured Gemini model first, then falls back through a small model chain if generation fails.
- **Markdown responses**: Assistant messages support GitHub-flavored Markdown and syntax-highlighted code blocks.
- **Simple chat UI**: React frontend includes loading states, clear-chat behavior, source tags, and light/dark theme switching.

## Tech Stack

### Frontend

- React 18
- TypeScript
- Vite
- TanStack Query
- superagent
- react-markdown
- react-syntax-highlighter
- react-hot-toast

### Backend

- FastAPI
- Uvicorn
- Pydantic
- SQLModel
- SQLite
- Google GenAI SDK
- LlamaIndex
- ChromaDB
- Gemini embeddings
- pypdf

## Project Structure

```text
ai-chatbot/
+-- client/
|   +-- apiClient.ts              # Frontend API client
|   +-- index.tsx                 # React entry point
|   +-- components/
|       +-- App.tsx               # Main chat screen
|       +-- ChatInput.tsx         # Message input form
|       +-- ChatMessage.tsx       # Message rendering, Markdown, sources
+-- server/
|   +-- main.py                   # FastAPI app, Gemini integration, chat routes
|   +-- database.py               # SQLite/SQLModel setup
|   +-- models.py                 # Chat message database model
|   +-- data/                     # SQLite DB, PDFs, and ChromaDB storage
|   +-- scripts/
|   |   +-- generate_mock_pdf.py
|   |   +-- ingest_docs.py        # PDF ingestion into the vector store
|   +-- services/
|       +-- rag_service.py        # ChromaDB/LlamaIndex retrieval service
+-- tests/
|   +-- client/                   # Vitest + Testing Library tests
|   +-- server/                   # Python API/RAG/database tests
+-- types/
|   +-- Message.ts                # Shared frontend message/source types
+-- docs/                         # Project write-ups
+-- package.json                  # Node scripts and frontend dependencies
+-- requirements.txt              # Python backend dependencies
+-- vite.config.js                # Vite config and API proxy
```

## Prerequisites

- Node.js 20 or newer
- Python 3.12 or newer
- A Google Gemini API key

## Environment Setup

Create a `.env` file in the project root. You can start from `.env.sample`.

```env
GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

`GEMINI_MODEL` is optional. If it is not set, the backend defaults to `gemini-2.5-flash`.

## Install Dependencies

Install frontend dependencies:

```bash
npm install
```

Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

## Run the App

Start both the Vite frontend and FastAPI backend:

```bash
npm run dev
```

Local services:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:3000`

The Vite dev server proxies `/api` requests to the backend.

## API Overview

### `GET /api/v1/messages`

Returns saved messages for a session.

Query parameters:

- `session_id`: optional, defaults to `default`

### `DELETE /api/v1/messages`

Deletes saved messages for a session.

Query parameters:

- `session_id`: optional, defaults to `default`

### `POST /api/v1/chat`

Sends a user message to the assistant.

Request body:

```json
{
  "message_id": "client-generated-message-id",
  "message": "What is the 5YA process?",
  "history": [],
  "session_id": "default"
}
```

Response body:

```json
{
  "id": "assistant-message-id",
  "reply": "Assistant response text",
  "sources": [
    {
      "file": "MOE_Property_Management_Handbook_Mock.pdf",
      "page": "1",
      "score": 0.92
    }
  ]
}
```

## RAG Workflow

1. Add PDF policy documents to `server/data/`.
2. Run the ingestion script to rebuild the ChromaDB collection.
3. Ask questions in the chat UI.
4. The backend retrieves the most relevant chunks, adds them to the Gemini prompt, and stores the final answer in SQLite.

The RAG service currently stores vectors under `server/data/chroma_db` and uses the `nz_school_policy` Chroma collection.

## Scripts

```bash
npm run dev          # Run frontend and backend together
npm run dev:client   # Run only the Vite frontend
npm run dev:python   # Run only the FastAPI backend
npm run build        # Build frontend assets
npm run test         # Run frontend tests
npm run test:watch   # Run frontend tests in watch mode
npm run lint         # Run ESLint
npm run format       # Format JS/TS files with Prettier
```

## Testing

Frontend tests live in `tests/client/` and use Vitest with Testing Library.

```bash
npm run test
```

Backend tests live in `tests/server/` and use Python's test tooling with FastAPI's `TestClient`.

```bash
python -m pytest tests/server
```

## Current Notes

- The app currently uses a single frontend session ID: `default`.
- The backend allows all CORS origins for development.
- RAG initialization requires `GOOGLE_GENERATIVE_AI_API_KEY` because Gemini embeddings are used.
- The included PDF and vector store are development/demo data.

## License

This project is licensed under the ISC License.
