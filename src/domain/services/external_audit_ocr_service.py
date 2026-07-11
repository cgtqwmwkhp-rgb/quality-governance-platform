"""OCR / native extraction pipeline for external audit import."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.domain.exceptions import ValidationError
from src.domain.models.document import FileType
from src.domain.services.document_extraction_service import extract_document_content
from src.domain.services.mistral_ocr_service import MistralOCRService

logger = logging.getLogger(__name__)

MAX_SOURCE_FILE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit

_EXTENSION_TO_FILETYPE = {
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".doc": FileType.DOC,
    ".xlsx": FileType.XLSX,
    ".xls": FileType.XLS,
    ".csv": FileType.CSV,
    ".txt": FileType.TXT,
    ".md": FileType.MD,
    ".png": FileType.PNG,
    ".jpg": FileType.JPG,
    ".jpeg": FileType.JPEG,
}


@dataclass
class ExternalAuditExtractionResult:
    """Merged native + OCR extraction for an import source document."""

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
    hard_ocr_failure: bool = False


class ExternalAuditOcrService:
    """Native document extraction + optional Mistral OCR with merge policy."""

    def __init__(self, ocr_service: MistralOCRService | None = None) -> None:
        self.ocr_service = ocr_service or MistralOCRService()

    @property
    def is_configured(self) -> bool:
        return self.ocr_service.is_configured

    @property
    def model(self) -> str | None:
        return getattr(self.ocr_service, "model", None)

    @staticmethod
    def _merge_extractions(
        *,
        native_text: str,
        native_pages: list[str],
        ocr_text: str,
        ocr_pages: list[str],
        native_method: str,
    ) -> tuple[str, list[str], str]:
        """Pick the richer extraction source, preferring OCR when it yields more content."""
        if not ocr_text:
            return native_text, native_pages, native_method
        if not native_text:
            return ocr_text, ocr_pages, "mistral_ocr"

        native_words = len(native_text.split())
        ocr_words = len(ocr_text.split())

        if ocr_words >= native_words * 1.15:
            logger.info(
                "OCR text chosen over native (%d vs %d words)",
                ocr_words,
                native_words,
            )
            return ocr_text, ocr_pages, "mistral_ocr"

        if native_words >= ocr_words * 1.15:
            return native_text, native_pages, native_method

        return ocr_text, ocr_pages, "mistral_ocr_preferred"

    def _infer_file_type(self, filename: str | None, content_type: str | None) -> FileType:
        suffix = Path(filename or "").suffix.lower()
        if suffix in _EXTENSION_TO_FILETYPE:
            return _EXTENSION_TO_FILETYPE[suffix]
        content_map = {
            "application/pdf": FileType.PDF,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
            "application/msword": FileType.DOC,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.XLSX,
            "application/vnd.ms-excel": FileType.XLS,
            "text/csv": FileType.CSV,
            "image/png": FileType.PNG,
            "image/jpeg": FileType.JPG,
        }
        inferred = content_map.get((content_type or "").lower())
        if inferred:
            return inferred
        raise ValidationError("Unsupported source document type for external audit import")

    async def extract(
        self,
        *,
        raw: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> ExternalAuditExtractionResult:
        """Run native extraction, optional OCR, and merge into a single text corpus."""
        file_type = self._infer_file_type(filename, content_type)
        extraction = extract_document_content(file_type, filename or "source", raw)
        native_text = extraction.text.strip()
        extraction_method = extraction.extraction_method
        page_texts = extraction.page_texts or []
        note = extraction.note

        ocr_text = ""
        ocr_pages: list[str] = []
        ocr_provider_status: str | None = None
        if self.ocr_service.is_configured:
            ocr_result = await self.ocr_service.ocr_bytes(
                raw,
                filename or "source",
                content_type or "application/octet-stream",
            )
            ocr_text = ocr_result.text.strip()
            ocr_pages = ocr_result.pages or []
            ocr_provider_status = ocr_result.provider_status
            if ocr_result.note and note is None:
                note = ocr_result.note

        hard_ocr_failure = ocr_provider_status == "failed" and not native_text and not ocr_text
        if hard_ocr_failure:
            return ExternalAuditExtractionResult(
                text="",
                page_texts=[],
                extraction_method=extraction_method,
                page_count=extraction.page_count,
                sheet_count=extraction.sheet_count,
                has_tables=bool(extraction.has_tables),
                note=note,
                ocr_provider_status=ocr_provider_status,
                native_text=native_text,
                ocr_text=ocr_text,
                hard_ocr_failure=True,
            )

        text, page_texts, extraction_method = self._merge_extractions(
            native_text=native_text,
            native_pages=page_texts,
            ocr_text=ocr_text,
            ocr_pages=ocr_pages,
            native_method=extraction_method,
        )
        return ExternalAuditExtractionResult(
            text=text,
            page_texts=page_texts,
            extraction_method=extraction_method,
            page_count=extraction.page_count or len(page_texts) or None,
            sheet_count=extraction.sheet_count,
            has_tables=bool(extraction.has_tables),
            note=note,
            ocr_provider_status=ocr_provider_status,
            native_text=native_text,
            ocr_text=ocr_text,
            hard_ocr_failure=False,
        )


__all__ = [
    "MAX_SOURCE_FILE_BYTES",
    "ExternalAuditExtractionResult",
    "ExternalAuditOcrService",
]
