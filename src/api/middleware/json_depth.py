"""JSON depth limiting middleware to prevent deeply nested payload attacks."""

import json
import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

MAX_JSON_DEPTH = 10

SKIP_METHODS = {"GET", "DELETE", "OPTIONS", "HEAD"}


def _check_depth(obj: Any, current: int = 1, limit: int = MAX_JSON_DEPTH) -> bool:
    """Return True if nesting depth exceeds `limit`."""
    if current > limit:
        return True
    if isinstance(obj, dict):
        return any(_check_depth(v, current + 1, limit) for v in obj.values())
    if isinstance(obj, list):
        return any(_check_depth(item, current + 1, limit) for item in obj)
    return False


class JsonDepthMiddleware(BaseHTTPMiddleware):
    """Reject JSON payloads nested deeper than MAX_JSON_DEPTH levels."""

    async def dispatch(self, request: Request, call_next):
        if request.method in SKIP_METHODS:
            return await call_next(request)

        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return await call_next(request)

        body = await request.body()
        if not body:
            return await call_next(request)

        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return await call_next(request)

        if _check_depth(parsed):
            logger.warning(
                "JSON depth exceeded",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "max_depth": MAX_JSON_DEPTH,
                },
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "JSON_DEPTH_EXCEEDED",
                    "detail": f"JSON nesting depth exceeds the maximum allowed ({MAX_JSON_DEPTH} levels).",
                },
            )

        return await call_next(request)
