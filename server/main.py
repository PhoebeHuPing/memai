"""FastAPI application entry point.

Initialises the app, registers middleware, exception handlers, and routers.
"""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.database import create_db_and_tables
from server.routers import chat, sessions
from server.schemas import ErrorResponse

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Unified error handling ---


def _status_to_error_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        404: "not_found",
        408: "timeout",
        429: "rate_limited",
        500: "internal_error",
        503: "service_unavailable",
    }
    return mapping.get(status_code, f"http_{status_code}")


@app.exception_handler(HTTPException)
async def unified_http_exception_handler(request: Request, exc: HTTPException):
    """Convert all HTTPExceptions to a consistent ErrorResponse format."""
    error_code = _status_to_error_code(exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=error_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unified_generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="internal_error",
            message="An unexpected error occurred. Please try again.",
            detail=str(exc) if os.getenv("DEBUG") else None,
        ).model_dump(),
    )


# --- Register routers ---
app.include_router(sessions.router)
app.include_router(chat.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
