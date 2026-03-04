"""Rate limiting middleware for API protection."""

import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimiter:
    """In-memory token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.buckets: Dict[str, Tuple[float, int]] = defaultdict(
            lambda: (time.time(), requests_per_minute)
        )

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        last_check, tokens = self.buckets[key]
        elapsed = now - last_check
        tokens = min(self.rpm, tokens + int(elapsed * self.rpm / 60))
        if tokens > 0:
            self.buckets[key] = (now, tokens - 1)
            return True
        self.buckets[key] = (now, 0)
        return False


_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/healthz") or request.url.path.startswith(
            "/readyz"
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if not _limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
