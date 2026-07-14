"""Environment-gated Azure Document Intelligence integration scaffold.

This module intentionally makes no outbound calls. A production adapter can
replace ``analyze_document`` once Azure credential and tenancy controls are
approved, while callers already have a stable result contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


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
]
