"""Carrier for the request attributes an audit entry needs but the domain cannot ask for.

``ip_address`` and ``user_agent`` live on ``AuditLogEntry`` and were null on every
row, because the only place they exist is the HTTP request and
``record_audit_event`` is a domain function that must not import FastAPI or the
infrastructure request context. Threading them through 71 call sites as
parameters would have put a transport detail into the signature of every domain
service that records an event, so they travel out of band instead.

The mechanism is the one already used for request-scoped values in this
repository — a ``ContextVar`` set by middleware and read further down, as
``src/infrastructure/middleware/tenant_context.py`` does for the tenant id. This
module deliberately copies that module's shape: ``set_*`` returns a
:class:`~contextvars.Token` and ``reset_*`` consumes it, so the value is unwound
on the way out rather than overwritten on the way in.

**This module lives in the domain layer on purpose.** Putting it under
``src/infrastructure`` would mean ``audit_service`` importing infrastructure
request context, which is precisely the coupling that kept these two fields out
of PR #1381 (D09). Here the dependency runs the other way: the domain declares
what it needs, and the HTTP layer — which already holds a ``Request`` — fills it
in. Nothing in this file imports anything outside the standard library, so it is
safe to import from anywhere.

Absence is normal, not exceptional. A Celery worker, a startup hook, a CLI
command and a unit test all have no request, so the getter returns ``None`` and
the audit row keeps a null ``ip_address`` the same way it does today. That is the
right outcome: inventing a placeholder like ``"127.0.0.1"`` would put a false
statement into a compliance record. Nothing here raises, so a missing request
context can never turn into a refused mutation.
"""

from __future__ import annotations

import dataclasses
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

# Bounded to the widths of AuditLogEntry.ip_address / user_agent. Truncation
# happens here rather than at the write so an oversized header cannot raise a
# DataError on flush: record_audit_event now fails closed, so a 900-character
# User-Agent would otherwise refuse the business mutation it was only supposed to
# annotate. A clipped user agent is a cosmetic loss; a rejected incident update
# is not.
IP_ADDRESS_MAX_LENGTH = 45
USER_AGENT_MAX_LENGTH = 500


@dataclasses.dataclass(frozen=True)
class AuditRequestContext:
    """The request-scoped attributes an audit entry records about its origin.

    Frozen so that a value handed to one audit event cannot be mutated by the
    next one in the same request.
    """

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


_EMPTY = AuditRequestContext()

_audit_request_context: ContextVar[Optional[AuditRequestContext]] = ContextVar(
    "audit_request_context",
    default=None,
)


def _clean(value: Optional[str], max_length: int) -> Optional[str]:
    """Normalise a header value to something storable, or ``None``.

    Whitespace-only and empty headers become ``None`` rather than ``""``: a null
    reads as "not captured", while an empty string reads as "captured, and the
    client had no address", which is not true of either case.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:max_length]


def build_audit_request_context(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditRequestContext:
    """Build a normalised, length-bounded context from raw header values."""
    return AuditRequestContext(
        ip_address=_clean(ip_address, IP_ADDRESS_MAX_LENGTH),
        user_agent=_clean(user_agent, USER_AGENT_MAX_LENGTH),
    )


def get_audit_request_context() -> AuditRequestContext:
    """Return the current request's audit context, or an empty one.

    Never ``None`` and never raises, so callers outside a request (Celery, beat
    schedules, startup, tests) need no special case: they read ``None`` for both
    fields, which is what the column should hold when there was no request.
    """
    return _audit_request_context.get() or _EMPTY


def set_audit_request_context(context: Optional[AuditRequestContext]) -> Token:
    """Bind *context* for the current context; returns a token for :func:`reset`."""
    return _audit_request_context.set(context)


def reset_audit_request_context(token: Token) -> None:
    """Unwind a previous :func:`set_audit_request_context` using its token.

    Resetting by token rather than setting ``None`` is what keeps a pooled or
    reused worker from serving the previous request's IP address to the next one:
    the variable returns to whatever it held before, including "unset".
    """
    _audit_request_context.reset(token)


@contextmanager
def audit_request_context(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Iterator[AuditRequestContext]:
    """Bind an audit request context for the duration of the block.

    The ``finally`` is the point of the helper: any caller that binds the context
    manually and forgets to reset it leaks one request's client address into
    whatever the same worker handles next.
    """
    context = build_audit_request_context(ip_address=ip_address, user_agent=user_agent)
    token = set_audit_request_context(context)
    try:
        yield context
    finally:
        reset_audit_request_context(token)
