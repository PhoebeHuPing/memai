"""Gemini model interaction with timeout, retry, and fallback logic."""

import asyncio
import os

from fastapi import HTTPException
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- Client setup ---
api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
if not api_key:
    print("Warning: GOOGLE_GENERATIVE_AI_API_KEY not found")
    client = None
else:
    client = genai.Client(api_key=api_key)

# --- Model configuration ---
gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
print(f"Gemini model configured: {gemini_model}")

fallback_models: list[str] = []
if gemini_model:
    fallback_models.append(gemini_model)
for model_candidate in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"]:
    if model_candidate not in fallback_models:
        fallback_models.append(model_candidate)
print(f"Model fallback chain: {fallback_models}")

# --- Timeout/retry configuration ---
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_RETRY_BASE_DELAY = float(os.getenv("GEMINI_RETRY_BASE_DELAY", "1.0"))

SYSTEM_PROMPT = """You are MemAI, a specialist assistant for New Zealand school property management.
You answer questions based on MOE (Ministry of Education) policy documents.

Rules:
- Base your answers on the provided context from MOE documents.
- Always cite your sources with the document name and page number.
- If the context doesn't contain enough information, say so clearly.
- Use NZ-specific terminology (5YA, 10YPP, SFIS, etc.) naturally.
- Format responses in Markdown for readability."""


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an exception indicates a retryable condition (429/503)."""
    exc_str = str(exc).lower()
    if "429" in exc_str or "resource exhausted" in exc_str:
        return True
    if "503" in exc_str or "service unavailable" in exc_str or "overloaded" in exc_str:
        return True
    return False


async def _generate_with_timeout(model_name: str, contents: list) -> object:
    """Call Gemini generate_content with a timeout.

    The Google GenAI SDK client.models.generate_content is synchronous,
    so we run it in an executor and wrap with asyncio.wait_for for timeout.
    """
    loop = asyncio.get_event_loop()

    async def _call():
        return await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(model=model_name, contents=contents),
        )

    return await asyncio.wait_for(_call(), timeout=GEMINI_TIMEOUT_SECONDS)


async def generate_with_retry_and_fallback(contents: list) -> object:
    """Try each model in the fallback chain with per-model exponential backoff retries.

    For each model:
    - On retryable errors (429/503): retry up to GEMINI_MAX_RETRIES times with exponential backoff.
    - On timeout: move to the next model immediately (no retry).
    - On other errors: move to the next model immediately.

    Raises HTTPException if all models exhausted.
    """
    tried_models: list[str] = []
    last_error: Exception | None = None

    for model_name in fallback_models:
        for attempt in range(GEMINI_MAX_RETRIES + 1):
            try:
                print(
                    f"Attempting model={model_name}, attempt={attempt + 1}/{GEMINI_MAX_RETRIES + 1}"
                )
                response = await _generate_with_timeout(model_name, contents)
                print(f"Successfully generated with model: {model_name}")
                return response
            except asyncio.TimeoutError:
                print(
                    f"Timeout: model={model_name} did not respond within {GEMINI_TIMEOUT_SECONDS}s"
                )
                last_error = TimeoutError(
                    f"Model {model_name} timed out after {GEMINI_TIMEOUT_SECONDS}s"
                )
                tried_models.append(model_name)
                break  # Don't retry timeouts, move to next model
            except Exception as e:
                last_error = e
                if _is_retryable_error(e) and attempt < GEMINI_MAX_RETRIES:
                    delay = GEMINI_RETRY_BASE_DELAY * (2**attempt)
                    print(
                        f"Retryable error on {model_name} (attempt {attempt + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    print(f"Non-retryable or exhausted retries for {model_name}: {e}")
                    tried_models.append(model_name)
                    break

    # All models failed
    if isinstance(last_error, TimeoutError):
        raise HTTPException(
            status_code=408,
            detail=f"All models timed out. Tried: {', '.join(tried_models)}",
        )
    elif last_error and _is_retryable_error(last_error):
        raise HTTPException(
            status_code=429,
            detail=f"Service is busy. All models ({', '.join(tried_models)}) returned rate limit or overload errors.",
        )
    else:
        raise HTTPException(
            status_code=503,
            detail=f"All models ({', '.join(tried_models)}) failed. Last error: {str(last_error)}",
        )
