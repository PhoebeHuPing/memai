# Integrating Google Gemini into a Full-Stack Chatbot: What the Docs Don't Tell You

> I wired up Gemini 2.0 Flash to a FastAPI backend and a React frontend. It took 70 lines of Python. The interesting part was everything around those 70 lines.

---

## Starting Point: A Chat UI With Nothing Behind It

I had a React frontend with a message list, an input box, and a send button. Messages rendered, state updated, the UI was smooth. But pressing "Send" did exactly nothing useful — there was no brain behind the interface.

The goal: plug in Google's Gemini API so the bot actually *thinks*.

Sounds trivial. "Just call the API." Except the gap between a working API call in a notebook and a production-ready integration in a full-stack app is where all the learning lives.

---

## The SDK Choice: `google-genai` (Not `google-generativeai`)

Google has multiple Python SDKs for Gemini. This tripped me up initially.

- `google-generativeai` — the older, widely-documented one
- `google-genai` — the newer, unified SDK

I went with `google-genai`. It uses a client-based pattern that felt cleaner:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)
```

No global configuration. No `genai.configure()` calls polluting module state. Instantiate a client, pass it around, done. Easier to test, easier to reason about.

---

## The Core Integration: 70 Lines That Matter

Here's the entire backend — `server/main.py`:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GOOGLE_GENERATIVE_AI_API_KEY"))

class Message(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    timestamp: Optional[int] = None

class ChatRequest(BaseModel):
    message: str
    history: List[Message]

@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    # Convert history to Gemini's format
    contents = []
    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    # Add current message
    contents.append(types.Content(role="user", parts=[types.Part(text=request.message)]))

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents
    )

    return {"reply": response.text}
```

That's it. No streaming, no tool-calling, no function declarations. Just: receive history → format → send → return text.

But even this "simple" code has several non-obvious decisions baked in.

---

## Decision 1: Conversation History Lives on the Client

The frontend sends the **entire conversation history** with every request:

```typescript
// apiClient.ts
export async function sendMessage(
  message: string,
  history: Message[],
): Promise<string> {
  const response = await request
    .post(`${rootUrl}/chat`)
    .send({ message, history })
  return response.body.reply
}
```

The backend is stateless. It doesn't store sessions, doesn't track who's talking, doesn't manage conversation threads. The client owns the state, the server just processes it.

**Why this works for an MVP:**
- Zero server-side storage needed
- No session management complexity
- Easy to test — send any history, get a response
- Clear separation: frontend handles UX, backend handles AI

**Why it won't scale:**
- Payload grows linearly with conversation length
- Eventually hits Gemini's context window limit
- No persistence across devices or browsers

But for an MVP? Perfect tradeoff.

---

## Decision 2: Role Mapping — `assistant` ≠ `model`

Subtle bug that cost me 30 minutes: the frontend uses `role: "assistant"` (standard chat convention), but Gemini expects `role: "model"`.

```python
role = "user" if msg.role == "user" else "model"
```

One ternary. But if you miss it, every multi-turn conversation breaks silently — Gemini ignores messages with unknown roles instead of erroring. You get responses that seem to have no memory of prior context.

Lesson: **always read the SDK's type definitions, not just the examples.**

---

## Decision 3: Fail-Fast on Missing API Key

```python
api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
if not api_key:
    print("Warning: GOOGLE_GENERATIVE_AI_API_KEY not found")
    client = None
```

Then in the endpoint:

```python
if not client:
    raise HTTPException(status_code=500, detail="API key not configured")
```

The app *starts* without a key (useful for running frontend-only dev). But the moment you hit the chat endpoint, it fails loudly. No cryptic `NoneType has no attribute 'models'` deep in the stack trace.

---

## The Frontend Glue: TanStack Query's `useMutation`

On the React side, I used TanStack Query's `useMutation` — not `useQuery`. This is a write operation (sending a message), not a read.

```typescript
const mutation = useMutation({
  mutationFn: async (content: string) => {
    const reply = await sendMessage(content, messages)
    return reply
  },
  onSuccess: (reply) => {
    const newMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: reply,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, newMessage])
  },
})
```

What this gives me for free:
- **`mutation.isPending`** — renders "AI is thinking..." with zero manual loading state
- **Automatic error handling** — no try/catch boilerplate in the component
- **Separation of concerns** — the component doesn't know how the API works

The user sends a message → optimistic append to message list → fire mutation → on success, append the AI response. Clean, predictable, testable.

---

## The Dev Experience: One Command to Rule Them All

```json
"scripts": {
  "dev": "run-p dev:client dev:python",
  "dev:client": "vite",
  "dev:python": "./.venv/bin/uvicorn server.main:app --reload --port 3000"
}
```

`npm run dev` starts both Vite (port 5173) and Uvicorn (port 3000) in parallel. Vite's proxy config forwards `/api` requests to the Python backend:

```javascript
server: {
  proxy: {
    '/api': 'http://localhost:3000',
  },
}
```

From the browser's perspective, everything lives on `localhost:5173`. No CORS issues during development (though I configured CORS on FastAPI anyway for production builds). No manual "start the backend first, then the frontend" dance.

---

## What Went Wrong Along the Way

### The `Content` / `Part` Type Confusion

Gemini's SDK uses a nested structure: `Content` contains `Part`s. My first attempt passed raw strings. The SDK accepted them silently (duck typing) but the model's responses were subtly worse — shorter, less contextual.

Explicitly constructing `types.Content(role=..., parts=[types.Part(text=...)])` fixed it. The lesson: just because the SDK doesn't throw an error doesn't mean you're doing it right.

### Model Name Versioning

The docs reference `gemini-1.5-flash`, but the latest available was `gemini-2.0-flash`. Model names aren't stable. I hardcoded it for now:

```python
model_id = "gemini-2.0-flash"
```

In production, this should be an environment variable. Models get deprecated. Names change. Your code shouldn't need a redeploy to switch.

### Response Handling — `response.text` Can Be None

If the model refuses to answer (safety filters, content policy), `response.text` returns `None` or throws. I wrapped it in a try/except that surfaces the actual error to the frontend rather than returning a 500 with no context.

---

## The Type Safety Bridge

One subtle win of this stack: the `Message` interface is defined once and used everywhere.

```typescript
// types/Message.ts
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}
```

On the Python side, Pydantic mirrors it:

```python
class Message(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    timestamp: Optional[int] = None
```

Not a shared schema in the formal sense (no code generation, no protobuf), but close enough. Change the shape on one side, the other side's validation catches it immediately.

---

## What I'd Do Differently Next Time

1. **Streaming from day one.** Gemini supports streaming responses. Waiting 2-3 seconds for a full response feels sluggish. Streaming the first token in 200ms would transform the UX.

2. **Environment-based model selection.** Hardcoded model names are tech debt. `MODEL_ID=gemini-2.0-flash` in `.env`.

3. **Conversation truncation.** Right now, I send *all* history. A 50-message conversation will eventually exceed the context window. Should implement a sliding window or summarization strategy.

4. **Structured error responses.** Currently returning raw exception strings. Should use a consistent error envelope: `{ "error": { "code": "...", "message": "..." } }`.

---

## TL;DR

Integrating Gemini into a full-stack app is straightforward — the SDK does the heavy lifting. The real work is in the decisions around it:

- Where does conversation state live? (Client, for now)
- How do you map between your app's types and the SDK's types? (Explicit role mapping)
- How do you handle the unhappy path? (Fail-fast, surface errors)
- How do you make the dev loop fast? (Parallel startup, proxy config)

The API call itself is one line. Everything else is engineering.

---

*Stack: FastAPI + google-genai SDK + React + TanStack Query + Vite.*
