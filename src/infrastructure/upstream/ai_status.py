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


def get_ocr_ops_capabilities() -> dict[str, Any]:
    """Return declared OCR ops capabilities without overstating DB readiness.

    This metadata endpoint deliberately does not acquire a database connection.
    The OCR-artifact schema is part of the application contract, but its
    presence in the deployed database is therefore declared rather than probed.
    """
    return {
        "ocr_artifacts_table": {
            "status": "declared",
            "schema_expected": True,
            "database_available": None,
            "probe": "not_run",
            "note": (
                "The application declares the ocr_artifacts schema, but this "
                "metadata endpoint does not probe the deployed database. "
                "database_available remains unknown until a database-backed "
                "OCR operation is exercised."
            ),
        },
        "page_consensus_persist": True,
        "dispute_ack_stubs": True,
        "dispute_ack_auth_required": True,
        "pipeline_version": "2026.07.r5",
        "provider_dial_on_probes": False,
        "endpoints": {
            "ocr_providers": "/api/v1/meta/ocr-providers",
            "ocr_capabilities": "/api/v1/meta/ocr-capabilities",
            "dispute": "/api/v1/meta/ocr-artifacts/dispute",
            "ack": "/api/v1/meta/ocr-artifacts/ack",
            "legacy_ocr_providers": "/api/v1/health/meta/ocr-providers",
            "legacy_ocr_capabilities": "/api/v1/health/meta/ocr-capabilities",
            "legacy_dispute": "/api/v1/health/meta/ocr-artifacts/dispute",
            "legacy_ack": "/api/v1/health/meta/ocr-artifacts/ack",
        },
        "e4_non_goal": (
            "Azure Document Intelligence production enablement (E4) is out of scope. "
            "Dispute/ack stubs record human overrides only; they never re-run OCR providers."
        ),
    }


def get_ocr_providers_readiness() -> dict[str, Any]:
    """Return OCR provider meta for ops dashboards (configuration only, no secrets).

    Aggregate ``status``:
    - ``configured``: Mistral + Gemini keys present (Azure DI reported separately)
    - ``partial``: at least one of Mistral/Gemini/Azure DI env groups present
    - ``not_configured``: no OCR-related credentials present
    """
    from src.infrastructure.external.azure_document_intelligence import get_azure_di_readiness

    ai = get_upstream_ai_readiness()
    azure_di = get_azure_di_readiness()

    mistral_configured = bool(ai["mistral"]["api_key_present"])
    gemini_configured = bool(ai["gemini"]["api_key_present"])
    azure_di_configured = bool(azure_di["configured"])
    azure_di_env_present = azure_di_configured or azure_di["status"] == "partial"

    if mistral_configured and gemini_configured:
        aggregate = "configured"
    elif mistral_configured or gemini_configured or azure_di_env_present:
        aggregate = "partial"
    else:
        aggregate = "not_configured"

    providers: dict[str, Any] = {
        "mistral": {
            **ai["mistral"],
            "configured": mistral_configured,
            "capabilities": [
                "external_audit_import_ocr",
                "scanned_pdf_fallback",
                "native_extraction_merge",
            ],
        },
        "gemini": {
            **ai["gemini"],
            "configured": gemini_configured,
            "capabilities": ["external_audit_import_review"],
        },
        "azure_di": azure_di,
    }

    payload: dict[str, Any] = {
        "status": aggregate,
        "providers": providers,
        "external_audit_import": {
            "ocr_configured": mistral_configured,
            "review_configured": gemini_configured,
            "native_extraction_always_available": True,
            "note": (
                "Native PDF/DOCX/XLSX extraction runs without OCR keys. "
                "Mistral OCR supplements scanned or image-heavy imports when configured."
            ),
        },
        "circuits": ai.get("circuits", {}),
        "ocr_ping": ai.get("ocr_ping"),
        "e4_non_goal": (
            "Azure Document Intelligence is not enabled in production. "
            "azure_di.* fields report env-var presence only; no outbound DI calls from probes."
        ),
        "capabilities": get_ocr_ops_capabilities(),
    }

    if aggregate == "not_configured":
        payload["note"] = (
            "No OCR providers configured. External audit import uses native extraction only. "
            "Set MISTRAL_API_KEY and GOOGLE_GEMINI_API_KEY when OCR/review is required."
        )
    elif aggregate == "partial" and not (mistral_configured and gemini_configured):
        missing = []
        if not mistral_configured:
            missing.append("MISTRAL_API_KEY")
        if not gemini_configured:
            missing.append("GOOGLE_GEMINI_API_KEY")
        if missing:
            payload["note"] = (
                "OCR providers partially configured. Missing: "
                + ", ".join(missing)
                + ". Import CUJs needing missing providers will degrade."
            )

    return payload
