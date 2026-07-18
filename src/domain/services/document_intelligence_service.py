"""Shared document intelligence spine for library uploads and reprocessing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document, FileType
from src.domain.services.document_extraction_service import extract_document_content
from src.domain.services.external_audit_ocr_service import ExternalAuditExtractionResult, ExternalAuditOcrService
from src.domain.services.scheme_profiles import canonical_scheme_id
from src.infrastructure.storage import storage_service

logger = logging.getLogger(__name__)

Purpose = Literal["library", "planet_mark", "external_audit", "uvdb", "customer_audit"]

_AUDIT_MERGE_PURPOSES = frozenset({"planet_mark", "external_audit", "uvdb", "customer_audit"})

# Native text below this word count is treated as thin/empty for library OCR fallback.
LIBRARY_THIN_NATIVE_WORD_THRESHOLD = 25


class _AzureDiClient(Protocol):
    @property
    def is_configured(self) -> bool: ...

    @property
    def enable_prod(self) -> bool: ...

    async def analyze_document(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ): ...


@dataclass
class DocumentIntelligenceResult:
    """Extraction output from the shared document intelligence spine."""

    text: str
    page_texts: list[str]
    extraction_method: str
    page_count: int | None = None
    sheet_count: int | None = None
    has_tables: bool = False
    note: str | None = None
    ocr_provider_status: str | None = None
    native_text: str = ""
    ocr_text: str = ""
    used_mistral_ocr: bool = False
    used_azure_di: bool = False
    hard_ocr_failure: bool = False


def _is_thin_native_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return len(stripped.split()) < LIBRARY_THIN_NATIVE_WORD_THRESHOLD


def _from_native_extraction(extraction) -> DocumentIntelligenceResult:
    page_texts = extraction.page_texts or []
    return DocumentIntelligenceResult(
        text=extraction.text.strip(),
        page_texts=page_texts,
        extraction_method=extraction.extraction_method,
        page_count=extraction.page_count or (len(page_texts) or None),
        sheet_count=extraction.sheet_count,
        has_tables=bool(extraction.has_tables),
        note=extraction.note,
        native_text=extraction.text.strip(),
    )


def purpose_for_assurance_scheme(scheme: str | None) -> Purpose:
    """Map audit run assurance scheme to document intelligence purpose."""
    canonical = canonical_scheme_id(scheme or "")
    if canonical == "achilles_uvdb":
        return "uvdb"
    if canonical == "customer_other":
        return "customer_audit"
    return "external_audit"


def _from_ocr_result(result: ExternalAuditExtractionResult) -> DocumentIntelligenceResult:
    return DocumentIntelligenceResult(
        text=result.text,
        page_texts=result.page_texts,
        extraction_method=result.extraction_method,
        page_count=result.page_count,
        sheet_count=result.sheet_count,
        has_tables=result.has_tables,
        note=result.note,
        ocr_provider_status=result.ocr_provider_status,
        native_text=result.native_text,
        ocr_text=result.ocr_text,
        used_mistral_ocr=bool(result.ocr_text or result.extraction_method.startswith("mistral")),
        hard_ocr_failure=result.hard_ocr_failure,
    )


class DocumentIntelligenceService:
    """Shared document intelligence: library thin-native policy + audit merge policy."""

    def __init__(
        self,
        ocr_service: ExternalAuditOcrService | None = None,
        azure_di_client: _AzureDiClient | None = None,
    ) -> None:
        self.ocr_service = ocr_service or ExternalAuditOcrService()
        self._azure_di_client = azure_di_client

    def _azure_client(self) -> _AzureDiClient:
        if self._azure_di_client is not None:
            return self._azure_di_client
        from src.domain.services.azure_document_intelligence_service import AzureDocumentIntelligenceClient

        self._azure_di_client = AzureDocumentIntelligenceClient()
        return self._azure_di_client

    @staticmethod
    def _mime_for_document(document: Document) -> str:
        if document.mime_type:
            return document.mime_type
        return f"application/{document.file_type.value}"

    async def _azure_di_failover(
        self,
        *,
        raw: bytes,
        filename: str,
        content_type: str | None,
        baseline: DocumentIntelligenceResult,
    ) -> DocumentIntelligenceResult:
        """DS-1b: when Mistral is missing/thin/failed, try Azure DI if E4-enabled."""
        client = self._azure_client()
        if not client.is_configured or not client.enable_prod:
            return baseline

        azure = await client.analyze_document(
            raw,
            filename,
            content_type or "application/pdf",
        )
        if getattr(azure, "provider_status", None) != "completed":
            note = getattr(azure, "note", None)
            if note:
                baseline.note = note if not baseline.note else f"{baseline.note}; {note}"
            return baseline

        azure_text = (getattr(azure, "text", "") or "").strip()
        if not azure_text:
            return baseline

        azure_pages = [page.text for page in getattr(azure, "pages", []) if getattr(page, "text", None)]
        if not azure_pages:
            azure_pages = [azure_text]

        baseline_words = len(baseline.text.split()) if baseline.text.strip() else 0
        azure_words = len(azure_text.split())
        if azure_words < max(LIBRARY_THIN_NATIVE_WORD_THRESHOLD, int(baseline_words * 1.05)):
            # Prefer existing text when Azure is not meaningfully richer.
            if baseline.text.strip() and not _is_thin_native_text(baseline.text):
                return baseline

        method = baseline.extraction_method
        if method and "azure_di" not in method:
            method = f"{method}+azure_di_failover" if method not in {"", "none"} else "azure_di_failover"
        else:
            method = "azure_di_failover"

        logger.info(
            "Azure DI failover selected for %s (%d vs %d words)",
            filename,
            azure_words,
            baseline_words,
        )
        return DocumentIntelligenceResult(
            text=azure_text,
            page_texts=azure_pages,
            extraction_method=method,
            page_count=len(azure_pages) or baseline.page_count,
            sheet_count=baseline.sheet_count,
            has_tables=baseline.has_tables or any(getattr(p, "table_count", 0) for p in getattr(azure, "pages", [])),
            note=baseline.note,
            ocr_provider_status="completed",
            native_text=baseline.native_text,
            ocr_text=azure_text,
            used_mistral_ocr=baseline.used_mistral_ocr,
            used_azure_di=True,
            hard_ocr_failure=False,
        )

    async def extract_bytes(
        self,
        *,
        raw: bytes,
        filename: str,
        content_type: str | None,
        file_type: FileType | None = None,
        purpose: Purpose = "library",
    ) -> DocumentIntelligenceResult:
        """Extract searchable text using purpose-specific native/OCR policy."""
        if purpose in _AUDIT_MERGE_PURPOSES:
            ocr_result = await self.ocr_service.extract(
                raw=raw,
                filename=filename,
                content_type=content_type,
            )
            result = _from_ocr_result(ocr_result)
            if result.hard_ocr_failure or _is_thin_native_text(result.text):
                result = await self._azure_di_failover(
                    raw=raw,
                    filename=filename,
                    content_type=content_type,
                    baseline=result,
                )
            return result

        resolved_file_type = file_type or self.ocr_service._infer_file_type(filename, content_type)
        native = extract_document_content(resolved_file_type, filename, raw)
        native_text = native.text.strip()

        if native_text and not _is_thin_native_text(native_text):
            return _from_native_extraction(native)

        if self.ocr_service.is_configured:
            ocr_result = await self.ocr_service.extract(
                raw=raw,
                filename=filename,
                content_type=content_type,
            )
            result = _from_ocr_result(ocr_result)
        else:
            result = _from_native_extraction(native)
            if _is_thin_native_text(native_text):
                thin_note = (
                    "Native extraction yielded thin or empty text; Mistral OCR is not configured "
                    "for library document fallback."
                )
                result.note = thin_note if not result.note else f"{result.note}; {thin_note}"

        if result.hard_ocr_failure or _is_thin_native_text(result.text):
            result = await self._azure_di_failover(
                raw=raw,
                filename=filename,
                content_type=content_type,
                baseline=result,
            )

        return result

    async def process(
        self,
        db: AsyncSession,
        document_id: int,
        *,
        purpose: Purpose = "library",
        content: bytes | None = None,
    ) -> DocumentIntelligenceResult:
        """Run library document intelligence for a stored document."""
        document = await db.get(Document, document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        raw = content
        if raw is None:
            raw = await storage_service().download(document.file_path)

        result = await self.extract_bytes(
            raw=raw,
            filename=document.file_name,
            content_type=self._mime_for_document(document),
            file_type=document.file_type if purpose == "library" else None,
            purpose=purpose,
        )

        document.page_count = result.page_count
        document.sheet_count = result.sheet_count
        document.has_tables = result.has_tables
        document.indexing_error = result.note
        if result.hard_ocr_failure:
            document.indexing_error = result.note or "OCR extraction failed with no native fallback text"

        return result


__all__ = [
    "DocumentIntelligenceResult",
    "DocumentIntelligenceService",
    "LIBRARY_THIN_NATIVE_WORD_THRESHOLD",
    "Purpose",
    "purpose_for_assurance_scheme",
]
