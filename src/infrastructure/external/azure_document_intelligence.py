"""Environment-gated Azure Document Intelligence integration.

E4 DPO gate: readiness/meta probes report configuration presence only and never
dial the service. Live analyze calls require BOTH credentials AND an explicit
``AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD`` flag. Without the flag, callers get
an honest ``stub_not_enabled`` result — credentials alone never enable OCR.
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


def _prod_enable_flag_set() -> bool:
    return (os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def get_azure_di_readiness() -> dict[str, Any]:
    """Return Azure Document Intelligence configuration status without secrets."""
    endpoint = (os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or "").strip()
    api_key = (os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or "").strip()
    endpoint_present = _present(endpoint)
    api_key_present = _present(api_key)
    configured = endpoint_present and api_key_present
    enable_flag = _prod_enable_flag_set()

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
        "enabled_in_prod": bool(configured and enable_flag),
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
    elif not enable_flag:
        payload["note"] = (
            "Azure DI credentials are present but the production adapter is not enabled "
            "(E4 DPO gate). Set AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD=true only after E4 "
            "DPO sign-off. Meta/readiness probes never transmit document content."
        )
    else:
        payload["note"] = (
            "Azure DI is configured and the prod-enable flag is set — the adapter will "
            "call the live API for document analysis requests. Readiness/meta probes "
            "still never transmit document content."
        )

    return payload


class AzureDocumentIntelligenceClient:
    """Credential-aware Azure DI adapter; network-free unless explicitly enabled."""

    _API_VERSION = "2024-11-30"
    _POLL_ATTEMPTS = 20
    _POLL_INTERVAL_SECONDS = 1.0
    _REQUEST_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        enable_prod: bool | None = None,
    ) -> None:
        self.endpoint = endpoint if endpoint is not None else os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
        self.api_key = api_key if api_key is not None else os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
        self.enable_prod = enable_prod if enable_prod is not None else _prod_enable_flag_set()

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint.strip() and self.api_key.strip())

    async def analyze_document(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> AzureDocumentIntelligenceResult:
        """Stub unless configured AND explicitly enabled; never raises on failure."""
        if not self.is_configured:
            return AzureDocumentIntelligenceResult(
                note=f"Azure Document Intelligence is not configured for {filename}.",
            )

        if not self.enable_prod:
            return AzureDocumentIntelligenceResult(
                provider_status="stub_not_enabled",
                note="Azure Document Intelligence credentials are configured, but the production adapter is not enabled.",
            )

        try:
            return await self._analyze_document_live(content, filename, content_type)
        except Exception as exc:  # noqa: BLE001
            return AzureDocumentIntelligenceResult(
                provider_status="failed",
                note=f"Azure Document Intelligence call failed for {filename} ({type(exc).__name__}).",
            )

    async def _analyze_document_live(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> AzureDocumentIntelligenceResult:
        import asyncio

        import httpx

        analyze_url = (
            f"{self.endpoint.rstrip('/')}/documentintelligence/documentModels/prebuilt-read:analyze"
            f"?api-version={self._API_VERSION}"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": content_type or "application/pdf",
        }

        async with httpx.AsyncClient(timeout=self._REQUEST_TIMEOUT_SECONDS) as client:
            submit_response = await client.post(analyze_url, headers=headers, content=content)
            submit_response.raise_for_status()
            operation_location = submit_response.headers.get("Operation-Location")
            if not operation_location:
                return AzureDocumentIntelligenceResult(
                    provider_status="failed",
                    note=f"Azure DI did not return an Operation-Location for {filename}.",
                )

            poll_headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            for _ in range(self._POLL_ATTEMPTS):
                await asyncio.sleep(self._POLL_INTERVAL_SECONDS)
                poll_response = await client.get(operation_location, headers=poll_headers)
                poll_response.raise_for_status()
                payload = poll_response.json()
                status = str(payload.get("status", "")).lower()
                if status == "succeeded":
                    return self._parse_analyze_result(payload)
                if status in {"failed", "canceled"}:
                    return AzureDocumentIntelligenceResult(
                        provider_status="failed",
                        note=f"Azure DI analysis {status} for {filename}.",
                    )

        return AzureDocumentIntelligenceResult(
            provider_status="failed",
            note=f"Azure DI analysis timed out waiting for a result for {filename}.",
        )

    @staticmethod
    def _parse_analyze_result(payload: dict[str, Any]) -> AzureDocumentIntelligenceResult:
        result = payload.get("analyzeResult") or {}
        raw_pages = result.get("pages") or []
        pages: list[AzureDocumentPage] = []
        for raw_page in raw_pages:
            lines = raw_page.get("lines") or []
            page_text = "\n".join(str(line.get("content", "")) for line in lines if line.get("content"))
            pages.append(
                AzureDocumentPage(
                    page_number=int(raw_page.get("pageNumber", len(pages) + 1)),
                    text=page_text,
                    table_count=len(result.get("tables") or []) if raw_page.get("pageNumber") == 1 else 0,
                )
            )
        if not pages and result.get("content"):
            pages.append(AzureDocumentPage(page_number=1, text=str(result.get("content", ""))))
        return AzureDocumentIntelligenceResult(pages=pages, provider_status="completed")


__all__ = [
    "AzureDocumentIntelligenceClient",
    "AzureDocumentIntelligenceResult",
    "AzureDocumentPage",
    "get_azure_di_readiness",
]
