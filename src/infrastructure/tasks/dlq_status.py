"""DLQ depth probe honesty for /readyz (informational only).

Never flips HTTP readiness. Distinguishes schema-missing (unavailable)
from unexpected probe failures (error).
"""

from __future__ import annotations

from typing import Any

_WARN_THRESHOLD = 10
_CRITICAL_THRESHOLD = 50


def _thresholds() -> dict[str, int]:
    return {
        "warn_threshold": _WARN_THRESHOLD,
        "critical_threshold": _CRITICAL_THRESHOLD,
    }


def dlq_depth_ok(depth: int) -> dict[str, Any]:
    return {"status": "ok", "depth": int(depth), **_thresholds()}


def is_missing_failed_tasks_relation(exc: BaseException) -> bool:
    """True when the failure is 'failed_tasks does not exist' (or equivalent)."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        pgcode = getattr(current, "pgcode", None)
        if pgcode == "42P01":
            return True
        name = type(current).__name__.lower()
        if "undefinedtable" in name:
            return True
        msg = str(current).lower()
        if "failed_tasks" in msg and (
            "does not exist" in msg
            or "no such table" in msg
            or "undefinedtable" in msg
            or "undefined table" in msg
        ):
            return True
        orig = getattr(current, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            current = orig
            continue
        cause = current.__cause__
        if isinstance(cause, BaseException) and id(cause) not in seen:
            current = cause
            continue
        break
    return False


def dlq_depth_from_exception(exc: BaseException) -> dict[str, Any]:
    """Map a probe exception to an honest informational status payload."""
    error_class = type(exc).__name__
    if is_missing_failed_tasks_relation(exc):
        return {
            "status": "unavailable",
            "depth": None,
            **_thresholds(),
            "error_class": error_class,
            "note": (
                "failed_tasks table is not present; DLQ depth cannot be measured "
                "until migrations apply."
            ),
        }
    return {
        "status": "error",
        "depth": None,
        **_thresholds(),
        "error_class": error_class,
    }
