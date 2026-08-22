"""Simple API key authentication middleware.

When the environment variable API_SECRET_KEY is set, all /api/ requests
must include the header:
    Authorization: Bearer <key>

If API_SECRET_KEY is not set, authentication is disabled (open access),
which is the default for local development.
"""

import os

from fastapi import HTTPException, Request


API_SECRET_KEY: str | None = os.getenv("API_SECRET_KEY")


def require_auth(request: Request) -> None:
    """FastAPI dependency that enforces bearer token authentication.

    Skips authentication when API_SECRET_KEY is not configured (dev mode).
    Raises HTTPException 401 on invalid/missing credentials.
    """
    if not API_SECRET_KEY:
        # Auth disabled — open access (development mode)
        return

    auth_header = request.headers.get("authorization", "")

    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Authorization: Bearer <key> header.",
        )

    # Expect "Bearer <token>"
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use: Authorization: Bearer <key>",
        )

    token = parts[1].strip()
    if token != API_SECRET_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )
