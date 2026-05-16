# 🧠 MemAI: Your Digital Memory Bank

> **"Capture every spark. A persistent AI companion that turns daily dialogue into a permanent personal knowledge base."**

MemAI is not just another chatbot. It's a **Second Brain** powered by Google's Gemini AI, designed to bridge the gap between fleeting conversations and lasting insights. Built with a high-performance **Python/FastAPI** backend and a sleek **React/TypeScript** frontend, MemAI helps you organize thoughts, archive wisdom, and recall information effortlessly.

---

## ✨ Key Features

*   **💾 Persistent Memory**: Your conversations aren't lost to a page refresh. MemAI uses intelligent archiving to keep your ideas safe.
*   **🤖 Gemini 1.5 Flash Powered**: Leverages the latest generative AI for lightning-fast, context-aware responses.
*   **🐍 FastAPI Backend**: A robust, modern Python infrastructure for handling complex AI logic and history.
*   **⚛️ Modern React UI**: A clean, distraction-free interface built for deep thinking and easy navigation.
*   **🛡️ Type-Safe Architecture**: Full TypeScript integration from frontend to API types.

---

## 🛠️ Tech Stack

- **Frontend**: [React 18](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [Vite](https://vitejs.dev/), [TanStack Query](https://tanstack.com/query/latest)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [Pydantic](https://docs.pydantic.dev/)
- **AI Engine**: [Google Gemini AI](https://ai.google.dev/) via `google-genai` SDK
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
├── client/           # React + TypeScript Frontend
│   ├── components/   # UI Components (App, Input, Message)
│   └── apiClient.ts  # API communication logic
├── server/           # Python + FastAPI Backend
│   └── main.py       # Main API routes and Gemini integration
├── types/            # Shared TypeScript interfaces
├── index.html        # Entry HTML
└── README.md         # You are here!
```

---

## 🗺️ Roadmap

- [ ] **Phase 1**: Implement LocalStorage persistence in the frontend.
- [ ] **Phase 2**: Add Markdown support and Syntax Highlighting for code.
- [ ] **Phase 3**: Integrate SQLite for server-side permanent storage.
- [ ] **Phase 4**: Add AI Personas (e.g., Researcher, Coder, Writer).
- [ ] **Phase 5**: Semantic Search across chat history.

---

## 📜 License

This project is licensed under the **ISC License**. Feel free to use, modify, and build upon it!

---
*Built as an advanced exploration of Full-Stack AI integration.*
