"""Shared Pydantic validators for input sanitization."""

from typing import Any

from src.infrastructure.sanitization import sanitize_html


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
