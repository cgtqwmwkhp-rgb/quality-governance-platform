"""Unit coverage for DocumentIntelligenceService library OCR spine."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.models.document import FileType
from src.domain.services.document_intelligence_service import (
    LIBRARY_THIN_NATIVE_WORD_THRESHOLD,
    DocumentIntelligenceService,
    purpose_for_assurance_scheme,
)
from src.domain.services.external_audit_ocr_service import ExternalAuditExtractionResult


@pytest.mark.asyncio
async def test_extract_bytes_skips_ocr_when_native_is_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    rich_text = " ".join(f"word{i}" for i in range(LIBRARY_THIN_NATIVE_WORD_THRESHOLD + 5))
    monkeypatch.setattr(
        "src.domain.services.document_intelligence_service.extract_document_content",
        lambda *_args, **_kwargs: SimpleNamespace(
            text=rich_text,
            page_texts=[rich_text],
            extraction_method="pdf_text",
            page_count=1,
            sheet_count=None,
            has_tables=False,
            note=None,
        ),
    )
    ocr_service = SimpleNamespace(
        is_configured=True,
        extract=AsyncMock(
            return_value=ExternalAuditExtractionResult(
                text="should-not-be-used",
                page_texts=["should-not-be-used"],
                extraction_method="mistral_ocr",
            )
        ),
    )
    service = DocumentIntelligenceService(ocr_service=ocr_service)

    result = await service.extract_bytes(
        raw=b"%PDF",
        filename="policy.pdf",
        content_type="application/pdf",
        file_type=FileType.PDF,
    )

    assert result.text == rich_text
    assert result.used_mistral_ocr is False
    ocr_service.extract.assert_not_called()


@pytest.mark.asyncio
async def test_extract_bytes_uses_mistral_when_native_is_thin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.domain.services.document_intelligence_service.extract_document_content",
        lambda *_args, **_kwargs: SimpleNamespace(
            text="scan artifact",
            page_texts=["scan artifact"],
            extraction_method="pdf_text",
            page_count=1,
            sheet_count=None,
            has_tables=False,
            note=None,
        ),
    )
    merged = ExternalAuditExtractionResult(
        text="Quality governance requires documented controls and review.",
        page_texts=["Quality governance requires documented controls and review."],
        extraction_method="mistral_ocr",
        native_text="scan artifact",
        ocr_text="Quality governance requires documented controls and review.",
    )
    ocr_service = SimpleNamespace(is_configured=True, extract=AsyncMock(return_value=merged))
    service = DocumentIntelligenceService(ocr_service=ocr_service)

    result = await service.extract_bytes(
        raw=b"%PDF",
        filename="scan.pdf",
        content_type="application/pdf",
        file_type=FileType.PDF,
    )

    assert result.text.startswith("Quality governance")
    assert result.used_mistral_ocr is True
    ocr_service.extract.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_updates_document_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    document = SimpleNamespace(
        id=9,
        file_name="scan.pdf",
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_path="documents/scan.pdf",
        page_count=None,
        sheet_count=None,
        has_tables=False,
        indexing_error=None,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=document)
    monkeypatch.setattr(
        "src.domain.services.document_intelligence_service.storage_service",
        lambda: SimpleNamespace(download=AsyncMock(return_value=b"%PDF")),
    )
    service = DocumentIntelligenceService(
        ocr_service=SimpleNamespace(
            is_configured=False,
            extract=AsyncMock(),
        )
    )
    monkeypatch.setattr(
        service,
        "extract_bytes",
        AsyncMock(
            return_value=SimpleNamespace(
                text="extracted",
                page_count=2,
                sheet_count=None,
                has_tables=True,
                note=None,
                hard_ocr_failure=False,
            )
        ),
    )

    result = await service.process(session, 9, purpose="library")

    assert result.text == "extracted"
    assert document.page_count == 2
    assert document.has_tables is True


def test_purpose_for_assurance_scheme_maps_uvdb_and_customer() -> None:
    assert purpose_for_assurance_scheme("achilles_uvdb") == "uvdb"
    assert purpose_for_assurance_scheme("customer_other") == "customer_audit"
    assert purpose_for_assurance_scheme("iso_9001") == "external_audit"
    assert purpose_for_assurance_scheme(None) == "external_audit"


@pytest.mark.asyncio
async def test_extract_bytes_azure_di_failover_when_mistral_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.domain.services.document_intelligence_service.extract_document_content",
        lambda *_args, **_kwargs: SimpleNamespace(
            text="scan",
            page_texts=["scan"],
            extraction_method="pdf_text",
            page_count=1,
            sheet_count=None,
            has_tables=False,
            note=None,
        ),
    )
    azure_pages = [SimpleNamespace(text="Azure recovered full scanned policy text for indexing.", table_count=0)]
    azure_client = SimpleNamespace(
        is_configured=True,
        enable_prod=True,
        analyze_document=AsyncMock(
            return_value=SimpleNamespace(
                provider_status="completed",
                text="Azure recovered full scanned policy text for indexing.",
                pages=azure_pages,
                note=None,
            )
        ),
    )
    service = DocumentIntelligenceService(
        ocr_service=SimpleNamespace(is_configured=False, extract=AsyncMock()),
        azure_di_client=azure_client,
    )

    result = await service.extract_bytes(
        raw=b"%PDF",
        filename="scan.pdf",
        content_type="application/pdf",
        file_type=FileType.PDF,
    )

    assert result.used_azure_di is True
    assert "Azure recovered" in result.text
    assert "azure_di" in result.extraction_method
    azure_client.analyze_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_bytes_audit_purpose_uses_merge_spine() -> None:
    merged = ExternalAuditExtractionResult(
        text="UVDB audit section scores and findings.",
        page_texts=["UVDB audit section scores and findings."],
        extraction_method="mistral_ocr",
        native_text="thin",
        ocr_text="UVDB audit section scores and findings.",
    )
    ocr_service = SimpleNamespace(
        is_configured=True,
        extract=AsyncMock(return_value=merged),
    )
    service = DocumentIntelligenceService(ocr_service=ocr_service)

    result = await service.extract_bytes(
        raw=b"%PDF",
        filename="uvdb-report.pdf",
        content_type="application/pdf",
        purpose="uvdb",
    )

    assert result.text.startswith("UVDB audit")
    assert result.used_mistral_ocr is True
    ocr_service.extract.assert_awaited_once()
