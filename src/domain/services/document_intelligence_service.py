"""Shared document intelligence spine for library uploads and reprocessing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document, FileType
from src.domain.services.document_extraction_service import extract_document_content
from src.domain.services.external_audit_ocr_service import ExternalAuditExtractionResult, ExternalAuditOcrService
from src.infrastructure.storage import storage_service

logger = logging.getLogger(__name__)

Purpose = Literal["library"]

# Native text below this word count is treated as thin/empty for library OCR fallback.
LIBRARY_THIN_NATIVE_WORD_THRESHOLD = 25


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
    """Library-facing document intelligence using native extract + optional Mistral OCR."""

    def __init__(self, ocr_service: ExternalAuditOcrService | None = None) -> None:
        self.ocr_service = ocr_service or ExternalAuditOcrService()

    @staticmethod
    def _mime_for_document(document: Document) -> str:
        if document.mime_type:
            return document.mime_type
        return f"application/{document.file_type.value}"

    async def extract_bytes(
        self,
        *,
        raw: bytes,
        filename: str,
        content_type: str | None,
        file_type: FileType,
        purpose: Purpose = "library",
    ) -> DocumentIntelligenceResult:
        """Extract searchable text, invoking Mistral OCR only when native text is empty/thin."""
        del purpose  # reserved for future purpose-specific policy hooks
        native = extract_document_content(file_type, filename, raw)
        native_text = native.text.strip()

        if native_text and not _is_thin_native_text(native_text):
            return _from_native_extraction(native)

        if not self.ocr_service.is_configured:
            result = _from_native_extraction(native)
            if _is_thin_native_text(native_text):
                thin_note = (
                    "Native extraction yielded thin or empty text; Mistral OCR is not configured "
                    "for library document fallback."
                )
                result.note = thin_note if not result.note else f"{result.note}; {thin_note}"
            return result

        ocr_result = await self.ocr_service.extract(
            raw=raw,
            filename=filename,
            content_type=content_type,
        )
        return _from_ocr_result(ocr_result)

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
            file_type=document.file_type,
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
]
