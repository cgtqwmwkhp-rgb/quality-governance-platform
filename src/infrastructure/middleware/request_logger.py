"""Structured request/response logging middleware."""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("request")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        request_id = getattr(request.state, "request_id", "-")
        user_id = getattr(request.state, "user_id", None)

        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": elapsed_ms,
                "user_id": user_id,
            },
        )

        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        return response
