"""W3C Trace Context (traceparent) storage via contextvars."""

import contextvars
import re
from typing import Optional

trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("span_id", default=None)
trace_flags_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_flags", default=None)

_TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})" r"-(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)


def parse_traceparent(header: str | None) -> bool:
    """Parse a W3C ``traceparent`` header and store values in contextvars.

    Returns *True* if parsing succeeded.
    """
    if not header:
        return False
    m = _TRACEPARENT_RE.match(header.strip())
    if not m:
        return False
    trace_id_var.set(m.group("trace_id"))
    span_id_var.set(m.group("span_id"))
    trace_flags_var.set(m.group("flags"))
    return True


def get_trace_id() -> Optional[str]:
    return trace_id_var.get()


def get_span_id() -> Optional[str]:
    return span_id_var.get()


def get_trace_flags() -> Optional[str]:
    return trace_flags_var.get()


def build_traceparent(
    trace_id: str,
    span_id: str,
    flags: str = "01",
    version: str = "00",
) -> str:
    """Build a W3C traceparent header value."""
    return f"{version}-{trace_id}-{span_id}-{flags}"
