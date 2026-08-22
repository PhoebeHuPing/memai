"""Simple in-memory rate limiting middleware.

Uses a sliding window counter per IP address. Not suitable for
multi-process deployments without a shared store (Redis), but
works well for single-instance deployments.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request


class RateLimiter:
    """Token-bucket-style rate limiter keyed by client IP.

    Args:
        requests_per_minute: Max requests allowed per minute per IP.
        burst: Extra burst capacity above the per-minute rate (default 5).
    """

    def __init__(self, requests_per_minute: int = 20, burst: int = 5):
        self.rate = requests_per_minute
        self.burst = burst
        self.window_seconds = 60
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup(self, key: str, now: float) -> None:
        """Remove timestamps older than the sliding window."""
        cutoff = now - self.window_seconds
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > cutoff
        ]

    def check(self, key: str) -> tuple[bool, int]:
        """Check if a request is allowed.

        Returns:
            (allowed, remaining) — whether the request is allowed and how
            many requests remain in the current window.
        """
        now = time.time()
        with self._lock:
            self._cleanup(key, now)
            count = len(self._requests[key])
            limit = self.rate + self.burst

            if count >= limit:
                return False, 0

            self._requests[key].append(now)
            return True, limit - count - 1

    def get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# Global rate limiter instances
# Chat endpoint: stricter (costs real API tokens)
chat_limiter = RateLimiter(requests_per_minute=10, burst=5)

# General API: more generous
general_limiter = RateLimiter(requests_per_minute=60, burst=20)


def require_rate_limit(
    request: Request,
    limiter: RateLimiter = general_limiter,
) -> None:
    """FastAPI dependency that enforces rate limiting.

    Raises HTTPException 429 if the client exceeds the limit.
    """
    client_ip = limiter.get_client_ip(request)
    allowed, remaining = limiter.check(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down and try again in a minute.",
        )
