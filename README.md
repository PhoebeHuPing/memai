# 🧠 MemAI: Your Digital Memory Bank

> **"Capture every spark. A persistent AI companion that turns daily dialogue into a permanent personal knowledge base."**

MemAI is not just another chatbot. It's a **Second Brain** powered by Google's Gemini AI, designed to bridge the gap between fleeting conversations and lasting insights. Built with a high-performance **Python/FastAPI** backend and a sleek **React/TypeScript** frontend, MemAI helps you organize thoughts, archive wisdom, and recall information effortlessly.

---

## ✨ Key Features

*   **💾 Persistent Memory**: Chats are saved both in LocalStorage and a SQLite database via SQLModel, ensuring durability across devices.
*   **🤖 Gemini 1.5 Flash Powered**: Uses Gemini 1.5/2.5 flash models with automatic fallback chain for reliability.
*   **🗂️ RAG Context Retrieval**: Chromadb-powered Retrieval‑Augmented Generation provides policy document context.
*   **🐍 FastAPI Backend**: A robust, modern Python infrastructure with async support and structured DB models.
*   **⚛️ Modern React UI**: A clean, distraction‑free interface built for deep thinking and easy navigation.
*   **🛡️ Type‑Safe Architecture**: Full TypeScript integration from frontend to API types.

---

## 🛠️ Tech Stack

- **Frontend**: [React 18](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [Vite](https://vitejs.dev/), [TanStack Query](https://tanstack.com/query/latest)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [Pydantic](https://docs.pydantic.dev/), [SQLModel (SQLite)](https://sqlmodel.tiangolo.com/)
- **AI Engine**: [Google Gemini AI](https://ai.google.dev/) via `google-genai` SDK
- **RAG**: [Chromadb](https://www.trychroma.com/) for vectorstore retrieval
- **Styling**: Modern Vanilla CSS with a focus on responsiveness

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: 3.12 or higher
- **Node.js**: 20.x or higher
- **API Key**: A [Google Gemini API Key](https://aistudio.google.com/app/apikey)

### 2. Installation

#### Clone and Install Frontend
```bash
npm install
```

#### Setup Python Environment
```bash
# Create a virtual environment
python -m venv .venv

# Activate it
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory (use `.env.sample` as a template):
```env
GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_api_key_here
```

### 4. Running the Application
Launch both the client and server with a single command:
```bash
npm run dev
```
- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://localhost:3000`

---

## 📂 Project Structure

```text
memai/
├── client/                     # React + TypeScript Frontend
│   ├── components/             # UI Components (App, Input, Message)
│   └── apiClient.ts            # API communication logic
├── server/                     # Python + FastAPI Backend
│   ├── main.py                 # API routes, Gemini integration
│   ├── database.py             # SQLite/SQLModel setup
│   ├── models.py               # DB ORM models
│   └── services/
│       └── rag_service.py      # Chromadb RAG implementation
├── types/                      # Shared TypeScript interfaces
├── index.html                  # Entry HTML
└── README.md                   # You are here!
```

---

## 🗺️ Roadmap

- [x] **Phase 1**: LocalStorage persistence (frontend) **and** backend SQLite storage via SQLModel.
- [x] **Phase 2**: Markdown rendering with syntax highlighting for code snippets.
- [x] **Phase 3**: SQLite integration completed; DB schema in `server/models.py`.
- [ ] **Phase 4**: AI Personas (e.g., Researcher, Coder, Writer).
- [ ] **Phase 5**: Semantic Search across chat history (future RAG enhancements).
- [ ] **Phase 6**: Retrieval‑Augmented Generation using Chromadb for policy‑document context.

---

## 📜 License

This project is licensed under the **ISC License**. Feel free to use, modify, and build upon it!

---
*Built as an advanced exploration of Full-Stack AI integration.*
