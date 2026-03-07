"""Helpers for structured API error payloads."""

from typing import Any


def api_error(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured detail payload for HTTPException."""
    return {
        "code": code,
        "message": message,
        "details": details or {},
    }
