"""Shared Pydantic validators for input sanitization."""

from datetime import datetime, timezone
from typing import Any

from src.infrastructure.sanitization import sanitize_html


def reject_future_statutory_datetime(value: datetime) -> datetime:
    """Reject statutory event/collision dates after today (UTC calendar day).

    Shared by near-miss, incident, and RTA create/update schemas (ACT-027 / PX-039).
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    if value.date() > datetime.now(timezone.utc).date():
        raise ValueError("Date must not be in the future")
    return value


def sanitize_field(v: Any) -> Any:
    """Sanitize a string value by stripping all HTML tags.

    Intended as a reusable helper called from ``@field_validator`` methods::

        @field_validator("title", "description", mode="before")
        @classmethod
        def _sanitize(cls, v):
            return sanitize_field(v)
    """
    if isinstance(v, str):
        return sanitize_html(v)
    return v
