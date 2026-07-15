"""Environment-gated Azure Document Intelligence integration scaffold.

This module intentionally makes no outbound calls. A production adapter can
replace ``analyze_document`` once Azure credential and tenancy controls are
approved, while callers already have a stable result contract.

E4 DPO gate: readiness helpers report configuration presence only; they never
enable Azure DI in production or dial the service from health/meta probes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AzureDocumentPage:
    """Text and table count reported for one 1-indexed document page."""

    page_number: int
    text: str
    table_count: int = 0


@dataclass(frozen=True)
class AzureDocumentIntelligenceResult:
    """Normalized outcome from the Azure Document Intelligence adapter."""

    pages: list[AzureDocumentPage] = field(default_factory=list)
    provider_status: str = "not_configured"
    note: str | None = None

    @property
    def text(self) -> str:
        """Return all non-empty page text in document order."""
        return "\n\n".join(page.text for page in self.pages if page.text).strip()


def _present(raw: str | None) -> bool:
    return bool((raw or "").strip())


def get_azure_di_readiness() -> dict[str, Any]:
    """Return Azure Document Intelligence configuration status without secrets."""
    endpoint = (os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or "").strip()
    api_key = (os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or "").strip()
    endpoint_present = _present(endpoint)
    api_key_present = _present(api_key)
    configured = endpoint_present and api_key_present

    if configured:
        status = "configured"
    elif endpoint_present or api_key_present:
        status = "partial"
    else:
        status = "not_configured"

    payload: dict[str, Any] = {
        "status": status,
        "configured": configured,
        "endpoint_present": endpoint_present,
        "api_key_present": api_key_present,
        "role": "dual_ocr_consensus",
        "enabled_in_prod": False,
        "capabilities": ["dual_ocr_consensus_scaffold"],
        "ping": {
            "status": "skipped",
            "connectivity": "unprobed",
            "note": "Azure DI ping is not executed on readiness/meta probes.",
        },
    }

    if status == "not_configured":
        payload["note"] = (
            "Azure Document Intelligence is not configured. Set "
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY "
            "when E4 dual-OCR is approved. E4 DPO gate: production adapter remains "
            "disabled; this endpoint reports env presence only."
        )
    elif status == "partial":
        missing = []
        if not endpoint_present:
            missing.append("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        if not api_key_present:
            missing.append("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        payload["note"] = (
            "Azure DI partially configured. Missing: "
            + ", ".join(missing)
            + ". Credentials alone do not enable production OCR."
        )
    else:
        payload["note"] = (
            "Azure DI credentials are present but the production adapter is not enabled "
            "(E4 DPO gate). Meta/readiness probes never transmit document content."
        )

    return payload


class AzureDocumentIntelligenceClient:
    """Credential-aware, network-free placeholder for Azure DI enablement."""

    def __init__(self, *, endpoint: str | None = None, api_key: str | None = None) -> None:
        self.endpoint = endpoint if endpoint is not None else os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
        self.api_key = api_key if api_key is not None else os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")

    @property
    def is_configured(self) -> bool:
        """Only allow Azure DI activation when both explicit environment values exist."""
        return bool(self.endpoint.strip() and self.api_key.strip())

    async def analyze_document(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> AzureDocumentIntelligenceResult:
        """Return a safe stub result without transmitting document content."""
        del content, content_type
        if not self.is_configured:
            return AzureDocumentIntelligenceResult(
                note=f"Azure Document Intelligence is not configured for {filename}.",
            )

        return AzureDocumentIntelligenceResult(
            provider_status="stub_not_enabled",
            note="Azure Document Intelligence credentials are configured, but the production adapter is not enabled.",
        )


__all__ = [
    "AzureDocumentIntelligenceClient",
    "AzureDocumentIntelligenceResult",
    "AzureDocumentPage",
    "get_azure_di_readiness",
]
