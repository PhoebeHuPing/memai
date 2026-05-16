# MemAI - AI Assistant Briefing

This document provides context for AI assistants helping maintain and extend **MemAI**.

## Project Overview

**MemAI** is a persistent AI assistant (a "Second Brain") built with a React/TypeScript frontend and a Python/FastAPI backend. It uses Google's Gemini AI to provide intelligent, context-aware responses and supports conversation persistence via browser LocalStorage.

## Key Architecture

1.  **Frontend**: React + TypeScript + TanStack Query.
    *   State management handles an array of `Message` objects.
    *   Persistence is implemented using `localStorage` to save and load messages.
2.  **Backend**: Python + FastAPI + `google-genai`.
    *   Endpoint: `POST /api/v1/chat`.
    *   Uses `gemini-1.5-flash` model.
    *   Maintains conversation context by passing history to the Gemini API.

## File Structure

*   `client/components/App.tsx`: Main chat interface and persistence logic.
*   `server/main.py`: FastAPI server handling AI requests.
*   `types/Message.ts`: TypeScript interface for messages.
*   `README.md`: Project documentation and setup instructions.

## Ongoing Goals

1.  **Enhance Persistence**: Move from LocalStorage to a backend database (e.g., SQLite).
2.  **UI/UX Improvements**: Add Markdown rendering, code highlighting, and better message styling.
3.  **Advanced Features**: Implement "Search History", "Export Chat", and custom AI personas.

## Environment Setup

*   API Key: `GOOGLE_GENERATIVE_AI_API_KEY` in `.env`.
*   Python: `.venv` with `fastapi`, `google-genai`, `python-dotenv`, `uvicorn`.
*   Node: `npm install` for frontend and build tools.

## Success Indicators

*   Chat messages persist across page reloads.
*   AI responses are contextually relevant.
*   Backend handles requests efficiently via FastAPI.
*   Clean, modern "Second Brain" aesthetic.

---
*Updated for the MemAI transition.*
