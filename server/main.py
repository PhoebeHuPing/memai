"""FastAPI application entry point.

Initialises the app, registers middleware, exception handlers, and routers.
"""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.database import create_db_and_tables
from server.logging_config import get_logger, setup_logging
from server.routers import chat, sessions
from server.schemas import ErrorResponse

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
    logger.error("Unhandled exception", exc_info=exc, extra={"path": str(request.url)})
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

# --- Serve frontend static files in production ---
_dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist")
if os.path.isdir(_dist_dir):
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist_dir, "assets")), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for any non-API route (SPA fallback)."""
        file_path = os.path.join(_dist_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_dist_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
