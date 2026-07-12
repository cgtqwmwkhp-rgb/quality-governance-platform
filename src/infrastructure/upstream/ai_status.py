"""OCR/AI upstream readiness helpers (Path-to-10 S10 honesty).

Mistral (OCR) and Gemini (review) are optional until operators set API keys.
Readiness reports configuration without secrets; missing keys stay
``not_configured`` and do not fail the probe.

OCR provider ping is an honest stub: /readyz never calls Mistral/Gemini.
Timeout + circuit metadata are surfaced when available.
"""

from __future__ import annotations

import os
from typing import Any

_AI_CIRCUIT_NAMES = ("mistral_analysis", "gemini_ai", "gemini_review", "document_ai")


def _present(raw: str | None) -> bool:
    return bool((raw or "").strip())


def _ocr_timeout_seconds() -> int:
    raw = (os.getenv("MISTRAL_OCR_TIMEOUT_SECONDS") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 120  # matches Settings.mistral_ocr_timeout_seconds default


def _ai_circuit_metadata() -> dict[str, Any]:
    """Return registered AI circuit health without inventing breaker state."""
    try:
        from src.infrastructure.resilience.circuit_breaker import get_all_circuits

        registered = {cb.name: cb.get_health() for cb in get_all_circuits()}
    except Exception:
        registered = {}

    circuits: dict[str, Any] = {}
    for name in _AI_CIRCUIT_NAMES:
        if name in registered:
            circuits[name] = registered[name]
        else:
            circuits[name] = {
                "name": name,
                "state": "unregistered",
                "note": "Circuit registers on first provider import/use in this process.",
            }
    return circuits


def get_upstream_ai_readiness() -> dict[str, Any]:
    """Return Mistral/Gemini configuration status without secrets.

    Status values (aggregate ``status``):
    - ``configured``: both Mistral and Gemini keys present
    - ``partial``: exactly one of Mistral/Gemini keys present
    - ``not_configured``: neither key present
    """
    mistral_key = (os.getenv("MISTRAL_API_KEY") or "").strip()
    gemini_key = (os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()

    mistral_configured = _present(mistral_key)
    gemini_configured = _present(gemini_key)
    timeout_seconds = _ocr_timeout_seconds()

    if mistral_configured and gemini_configured:
        status = "configured"
    elif mistral_configured or gemini_configured:
        status = "partial"
    else:
        status = "not_configured"

    # Honest OCR ping stub — never dials the provider from /readyz.
    ocr_ping = {
        "status": "skipped",
        "connectivity": "unprobed",
        "note": (
            "OCR provider ping is not executed on /readyz. "
            "Configuration and timeout/circuit metadata are reported instead; "
            "live OCR calls happen only on import/analysis paths."
        ),
    }

    payload: dict[str, Any] = {
        "status": status,
        "mistral": {
            "status": "configured" if mistral_configured else "not_configured",
            "api_key_present": mistral_configured,
            "role": "ocr",
            "timeout_seconds": timeout_seconds,
            "ping": ocr_ping,
        },
        "gemini": {
            "status": "configured" if gemini_configured else "not_configured",
            "api_key_present": gemini_configured,
            "role": "review",
            "ping": {
                "status": "skipped",
                "connectivity": "unprobed",
                "note": "Gemini ping is not executed on /readyz.",
            },
        },
        "circuits": _ai_circuit_metadata(),
        "ocr_ping": ocr_ping,
    }

    if status == "not_configured":
        payload["note"] = (
            "OCR/AI upstreams are not configured. Set MISTRAL_API_KEY and "
            "GOOGLE_GEMINI_API_KEY (Key Vault refs preferred) when document "
            "import OCR/review is required. Unset keys skip outbound AI calls."
        )
    elif status == "partial":
        missing = []
        if not mistral_configured:
            missing.append("MISTRAL_API_KEY")
        if not gemini_configured:
            missing.append("GOOGLE_GEMINI_API_KEY")
        payload["note"] = (
            "OCR/AI upstream partially configured. Missing: "
            + ", ".join(missing)
            + ". Import CUJs that need the missing provider will degrade."
        )
    return payload
