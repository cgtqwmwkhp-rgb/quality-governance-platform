"""Core middleware components for request processing."""

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestStateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to propagate request_id via request.state for reliable access.

    This middleware ensures request_id is available via request.state.request_id
    for all request handlers, dependencies, and services. This approach works
    reliably with both synchronous TestClient and asynchronous AsyncClient.

    The request_id is sourced from:
    1. X-Request-ID header (set by starlette-context RequestIdPlugin)
    2. Generated UUID if header is missing

    The request_id is then:
    - Stored in request.state.request_id for handler access
    - Added to response headers as X-Request-ID
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set request_id in request.state."""
        # Get or generate request_id BEFORE processing request
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4().hex)

        # Store in request.state for reliable access by handlers
        request.state.request_id = request_id

        # Process request (handlers can now access request.state.request_id)
        response = await call_next(request)

        # Ensure response has X-Request-ID header
        # (ContextMiddleware also sets this, but we ensure it's consistent)
        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request_id

        return response  # type: ignore[no-any-return]  # TYPE-IGNORE: MYPY-003 Starlette middleware call_next returns Any
