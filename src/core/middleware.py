"""Core middleware components for request processing."""

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.logging.context import set_request_id
from src.infrastructure.logging.trace_context import build_traceparent, get_trace_flags, get_trace_id, parse_traceparent


class RequestStateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to propagate request_id and W3C Trace Context.

    Handles:
    - ``X-Request-ID`` extraction / generation and contextvar storage
    - ``traceparent`` header parsing (W3C Trace Context) with trace_id / span_id
      stored in contextvars for downstream logging and outgoing HTTP propagation
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = uuid.uuid4().hex

        request.state.request_id = request_id
        set_request_id(request_id)

        traceparent = request.headers.get("traceparent")
        parse_traceparent(traceparent)

        response = await call_next(request)

        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request_id

        trace_id = get_trace_id()
        if trace_id:
            new_span = uuid.uuid4().hex[:16]
            flags = get_trace_flags() or "01"
            response.headers["traceparent"] = build_traceparent(trace_id, new_span, flags)

        return response  # type: ignore[no-any-return]  # TYPE-IGNORE: MYPY-003 Starlette middleware call_next returns Any
