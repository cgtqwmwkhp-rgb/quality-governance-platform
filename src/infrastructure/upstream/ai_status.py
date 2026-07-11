"""OCR/AI upstream readiness helpers (Path-to-10 S10 honesty).

Mistral (OCR) and Gemini (review) are optional until operators set API keys.
Readiness reports configuration without secrets; missing keys stay
``not_configured`` and do not fail the probe.
"""

from __future__ import annotations

import os
from typing import Any


def _present(raw: str | None) -> bool:
    return bool((raw or "").strip())


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

    if mistral_configured and gemini_configured:
        status = "configured"
    elif mistral_configured or gemini_configured:
        status = "partial"
    else:
        status = "not_configured"

    payload: dict[str, Any] = {
        "status": status,
        "mistral": {
            "status": "configured" if mistral_configured else "not_configured",
            "api_key_present": mistral_configured,
            "role": "ocr",
        },
        "gemini": {
            "status": "configured" if gemini_configured else "not_configured",
            "api_key_present": gemini_configured,
            "role": "review",
        },
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
