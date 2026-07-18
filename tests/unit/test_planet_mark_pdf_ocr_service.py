"""Unit tests for Planet Mark PDF OCR → year readings (Wave 1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.planet_mark_pdf_ocr_service import (
    APPLY_ACTION_APPLY,
    APPLY_ACTION_SKIP_NOT_EXTRACTED,
    APPLY_ACTION_SKIP_XLSX_SSOT,
    CONFIDENCE_HIGH,
    PlanetMarkOcrExtraction,
    PlanetMarkPdfOcrService,
    build_apply_plan,
    parse_fields_from_text,
)
from src.infrastructure.external.azure_document_intelligence import AzureDocumentIntelligenceResult

SAMPLE_REPORT = """
Planet Mark Measurement Report YE2024
Reporting period: 01 Apr 2023 to 31 Mar 2024

Total market based emissions: 654.459 tCO2e
Total per employee: 6.935 tCO2e
No. employees: 94.375

Certificate Number: PM-2024-88421
This organisation has been certified by Planet Mark.
"""


def test_parse_fields_extracts_totals_fte_and_certificate() -> None:
    fields, warnings = parse_fields_from_text(SAMPLE_REPORT)

    assert fields["total_co2e_tonnes"].value == "654.459"
    assert fields["total_co2e_tonnes"].confidence == CONFIDENCE_HIGH
    assert fields["co2e_per_fte"].value == "6.935"
    assert fields["average_fte"].value == "94.375"
    assert fields["certificate_number"].value == "PM-2024-88421"
    assert fields["reporting_period_label"].value == "YE2024"
    assert fields["certification_status_cue"].value == "certified"
    assert not any("Could not extract a total" in w for w in warnings)


def test_parse_fields_honesty_empty_when_no_numbers() -> None:
    fields, warnings = parse_fields_from_text("This PDF has no carbon figures.")

    assert fields["total_co2e_tonnes"].value is None
    assert fields["total_co2e_tonnes"].confidence == "none"
    assert fields["co2e_per_fte"].value is None
    assert any("Could not extract a total tCO2e" in w for w in warnings)


def test_parse_fields_rejects_ambiguous_totals() -> None:
    text = "Total emissions: 100 tCO2e\nTotal emissions: 250 tCO2e\n"
    fields, warnings = parse_fields_from_text(text)

    assert fields["total_co2e_tonnes"].value is None
    assert any("Multiple differing total" in w for w in warnings)


def test_build_apply_plan_skips_xlsx_ssot_unless_forced() -> None:
    extraction = PlanetMarkOcrExtraction(
        source_filename="report.pdf",
        document_kind="measurement_report",
        extraction_method="pdfplumber",
    )
    fields, _ = parse_fields_from_text(SAMPLE_REPORT)
    extraction.total_co2e_tonnes = fields["total_co2e_tonnes"]
    extraction.co2e_per_fte = fields["co2e_per_fte"]
    extraction.average_fte = fields["average_fte"]
    extraction.certificate_number = fields["certificate_number"]

    blocked = build_apply_plan(extraction, xlsx_ingested=True, force_overwrite_totals=False)
    by_field = {p.field_name: p for p in blocked}
    assert by_field["total_co2e_tonnes"].action == APPLY_ACTION_SKIP_XLSX_SSOT
    assert by_field["certificate_number"].action == APPLY_ACTION_APPLY

    forced = build_apply_plan(extraction, xlsx_ingested=True, force_overwrite_totals=True)
    by_field = {p.field_name: p for p in forced}
    assert by_field["total_co2e_tonnes"].action == APPLY_ACTION_APPLY


def test_build_apply_plan_skips_not_extracted() -> None:
    extraction = PlanetMarkOcrExtraction(
        source_filename="empty.pdf",
        document_kind="measurement_report",
        extraction_method="none",
    )
    plans = build_apply_plan(extraction, xlsx_ingested=False)
    assert all(p.action == APPLY_ACTION_SKIP_NOT_EXTRACTED for p in plans)


@pytest.mark.asyncio
async def test_service_uses_document_intelligence_spine() -> None:
    spine = SimpleNamespace(
        text=SAMPLE_REPORT,
        extraction_method="pdfplumber",
        note=None,
        hard_ocr_failure=False,
        ocr_provider_status=None,
    )
    intelligence = MagicMock()
    intelligence.extract_bytes = AsyncMock(return_value=spine)
    azure = MagicMock()
    azure.is_configured = False

    service = PlanetMarkPdfOcrService(intelligence_service=intelligence, azure_client=azure)
    result = await service.extract(
        content=b"%PDF-1.4 fake",
        filename="YE2024-report.pdf",
        content_type="application/pdf",
        document_kind="measurement_report",
    )

    intelligence.extract_bytes.assert_awaited_once()
    call_kwargs = intelligence.extract_bytes.await_args.kwargs
    assert call_kwargs["purpose"] == "planet_mark"
    assert result.total_co2e_tonnes.value == "654.459"
    assert result.extraction_method == "pdfplumber"
    assert result.has_any_extraction


@pytest.mark.asyncio
async def test_service_reports_azure_stub_honestly_when_configured() -> None:
    spine = SimpleNamespace(
        text=SAMPLE_REPORT,
        extraction_method="pdfplumber",
        note=None,
        hard_ocr_failure=False,
        ocr_provider_status=None,
    )
    intelligence = MagicMock()
    intelligence.extract_bytes = AsyncMock(return_value=spine)
    azure = MagicMock()
    azure.is_configured = True
    azure.analyze_document = AsyncMock(
        return_value=AzureDocumentIntelligenceResult(
            provider_status="stub_not_enabled",
            note="Azure Document Intelligence credentials are configured, but the production adapter is not enabled.",
        )
    )

    service = PlanetMarkPdfOcrService(intelligence_service=intelligence, azure_client=azure)
    result = await service.extract(
        content=b"%PDF",
        filename="report.pdf",
        content_type="application/pdf",
        document_kind="measurement_report",
    )

    assert any("not enabled" in w for w in result.warnings)
    assert result.total_co2e_tonnes.value == "654.459"
