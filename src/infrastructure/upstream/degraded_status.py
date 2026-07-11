"""Preferred upstream degraded summary for /readyz (Path-to-10 S10).

Surfaces OPEN / HALF_OPEN Preferred circuit breakers without dialing providers,
inventing secrets, or failing the readiness probe.
"""

from __future__ import annotations

from typing import Any


def get_upstream_degraded_readiness() -> dict[str, Any]:
    """Return banner-friendly degraded summary for Preferred upstream breakers.

    Honesty rules:
    - Does **not** register missing breakers (cold processes stay ``unregistered``).
    - Does **not** call OCR/AI/blob providers.
    - Does **not** invent API keys or SMTP credentials.
    - Informational only — callers must not flip ``/readyz`` HTTP status on this.
    """
    try:
        from src.domain.services.upstream_circuit_breaker import upstream_degraded_summary

        summary = upstream_degraded_summary(register_missing=False)
        payload = summary.as_dict()
    except Exception as exc:  # pragma: no cover - defensive readiness path
        return {
            "status": "error",
            "degraded": False,
            "open_circuits": [],
            "half_open_circuits": [],
            "circuits": [],
            "message": "Upstream degraded summary unavailable.",
            "note": f"Failed to read Preferred circuit registry: {type(exc).__name__}",
            "affects_readiness": False,
        }

    payload["status"] = "degraded" if payload["degraded"] else "ok"
    payload["affects_readiness"] = False
    payload["note"] = (
        "Preferred upstream circuit aggregate is informational. "
        "OPEN/HALF_OPEN circuits do not fail /readyz; "
        "live provider connectivity is never probed here."
    )
    return payload
