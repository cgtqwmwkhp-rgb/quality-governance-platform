"""Core middleware components for request processing."""

import uuid
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.security import decode_token
from src.domain.context.audit_request_context import (
    build_audit_request_context,
    reset_audit_request_context,
    set_audit_request_context,
)


def client_ip_of(request: Request) -> Optional[str]:
    """Best-effort client address for an audit record.

    Prefers the first hop in ``X-Forwarded-For`` because the application runs
    behind a proxy, where ``request.client.host`` is the proxy and recording it
    would put the same address on every entry — which looks populated but
    identifies nobody. Matches how ``rate_limiter.get_client_key`` already reads
    the client address, so the two cannot disagree about who made a request.

    The header is client-controlled and therefore spoofable. That is acceptable
    for an audit annotation and is not acceptable for an authorisation decision;
    nothing here is used for the latter.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    return request.client.host if request.client else None


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

    When a valid Bearer token is present, the authenticated user id is also
    exposed via request.state.user_id so trusted middleware can make
    authorization decisions without relying on client-supplied identity headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set request_id in request.state."""
        # Get or generate request_id BEFORE processing request
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4().hex)

        # Store in request.state for reliable access by handlers
        request.state.request_id = request_id
        request.state.user_id = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            payload = decode_token(token)
            user_id = payload.get("sub") if payload else None
            if user_id is not None:
                request.state.user_id = str(user_id)

        # Carry the client address and user agent to record_audit_event, which is
        # a domain function and cannot be handed a Request. Reset by token in
        # `finally` so a worker that serves the next request after this one does
        # not inherit this client's address (PX-142b).
        audit_token = set_audit_request_context(
            build_audit_request_context(
                ip_address=client_ip_of(request),
                user_agent=request.headers.get("User-Agent"),
            )
        )
        try:
            # Process request (handlers can now access request.state.request_id)
            response = await call_next(request)

            # Ensure response has X-Request-ID header
            # (ContextMiddleware also sets this, but we ensure it's consistent)
            if "X-Request-ID" not in response.headers:
                response.headers["X-Request-ID"] = request_id

            return response  # type: ignore[no-any-return]  # TYPE-IGNORE: MYPY-003 Starlette middleware call_next returns Any
        finally:
            reset_audit_request_context(audit_token)
