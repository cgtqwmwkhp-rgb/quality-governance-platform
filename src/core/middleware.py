"""Core middleware components for request processing."""

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.logging.context import set_request_id


class RequestStateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to propagate request_id via request.state and contextvars.

    This middleware ensures request_id is available via request.state.request_id
    for all request handlers, dependencies, and services. This approach works
    reliably with both synchronous TestClient and asynchronous AsyncClient.

    The request_id is sourced from:
    1. X-Request-ID header (set by starlette-context RequestIdPlugin)
    2. Generated UUID if header is missing

    The request_id is then:
    - Stored in request.state.request_id for handler access
    - Stored in a contextvar for access anywhere in the call stack
    - Added to response headers as X-Request-ID
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set request_id in request.state."""
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4().hex)

        request.state.request_id = request_id
        set_request_id(request_id)

        response = await call_next(request)

        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request_id

        return response  # type: ignore[no-any-return]  # TYPE-IGNORE: MYPY-003 Starlette middleware call_next returns Any
