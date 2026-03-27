"""Mistral OCR integration for scanned or image-heavy audit reports."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Normalized OCR result."""

    text: str
    pages: list[str] = field(default_factory=list)
    method: str = "mistral"
    provider_status: str = "completed"
    note: str | None = None


class MistralOCRService:
    """Best-effort OCR integration with configuration guard rails."""

    def __init__(self) -> None:
        self.api_key = settings.mistral_api_key
        self.base_url = settings.mistral_api_base_url.rstrip("/")
        self.model = settings.mistral_ocr_model
        self.timeout_seconds = settings.mistral_ocr_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool((self.api_key or "").strip())

    async def ocr_bytes(self, content: bytes, filename: str, content_type: str) -> OCRResult:
        """Return OCR text for files that native extraction could not parse.

        The provider integration is guarded so missing configuration or transient
        provider failures never create live findings or remediation side effects.
        """
        if not self.is_configured:
            logger.info("Mistral OCR skipped for %s because provider is not configured", filename)
            return OCRResult(
                text="",
                provider_status="not_configured",
                note="OCR provider is not configured.",
            )

        try:
            import base64

            import httpx

            encoded = base64.b64encode(content).decode("ascii")
            payload = {
                "model": self.model,
                "document": {
                    "type": "document_base64",
                    "document_base64": encoded,
                    "filename": filename,
                    "mime_type": content_type,
                },
                "include_image_base64": False,
            }
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/ocr",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
            data = response.json()
            pages = [(page.get("markdown") or page.get("text") or "").strip() for page in data.get("pages", [])]
            text = "\n\n".join(part for part in pages if part).strip()
            return OCRResult(
                text=text,
                pages=pages,
                provider_status="completed",
                note=None if text else "OCR completed but returned no text.",
            )
        except Exception as exc:
            logger.warning("Mistral OCR failed for %s: %s", filename, type(exc).__name__)
            return OCRResult(
                text="",
                provider_status="failed",
                note="OCR provider failed for this file; manual review is required.",
            )
