"""Unit tests for PAS 79 FRA OCR field extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.services.fra_pas79_ocr_service import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    FraPas79OcrService,
    _parse_uk_date,
    parse_fields_from_text,
)
from src.domain.services.ocr_field_extraction import CONFIDENCE_HIGH as SHARED_HIGH

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "fra"


def _sample() -> str:
    return (FIXTURES / "pas79_sample_report.txt").read_text(encoding="utf-8")


def _lmh() -> str:
    return (FIXTURES / "pas79_lmh_rating.txt").read_text(encoding="utf-8")


def test_parse_uk_date_day_first() -> None:
    assert _parse_uk_date("03/04/2027").isoformat() == "2027-04-03"
    assert _parse_uk_date("14 March 2026").isoformat() == "2026-03-14"
    assert _parse_uk_date("2026-03-14").isoformat() == "2026-03-14"
    assert _parse_uk_date("30/04/26").isoformat() == "2026-04-30"
    assert _parse_uk_date("30/04/99") is None  # yy > 79 rejected


def test_parse_sample_report_fields_and_actions() -> None:
    fields, actions, warnings = parse_fields_from_text(_sample())

    assert fields["assessment_date"]["value"] == "2026-03-14"
    assert fields["assessment_date"]["confidence"] == CONFIDENCE_HIGH
    assert fields["next_review_date"]["value"] == "2027-03-14"
    assert fields["review_interval_months"]["value"] == "12"
    assert fields["assessor_name"]["value"] == "Angela Rowntree"
    assert fields["assessor_organisation"]["value"] == "Northgate Fire Safety Consultants Ltd"
    assert fields["premises_name"]["value"] and "Plantexpand Depot" in fields["premises_name"]["value"]
    assert fields["pas79_reference"]["value"] == "FRA-2026-0417"
    assert fields["overall_risk_rating"]["value"] == "moderate"
    assert fields["risk_vocabulary"] == "pas79"

    assert len(actions) == 6
    assert actions[0].priority_normalised == "high"
    assert actions[0].target_date is not None
    assert actions[0].target_date.isoformat() == "2026-04-30"
    assert "FD30S" in actions[0].text  # continuation line appended
    assert actions[1].target_date is None
    assert actions[1].target_date_raw and actions[1].target_date_raw.lower().startswith("immediate")
    assert actions[5].needs_review is True
    assert actions[5].priority_raw is None
    assert actions[5].confidence == CONFIDENCE_NONE
    assert not any("No Priority Action Plan" in w for w in warnings)


def test_parse_lmh_vocabulary_not_cross_mapped() -> None:
    fields, _actions, _warnings = parse_fields_from_text(_lmh())
    assert fields["overall_risk_rating"]["value"] == "medium"
    assert fields["risk_vocabulary"] == "lmh"


def test_parse_empty_text_fail_soft() -> None:
    fields, actions, warnings = parse_fields_from_text("")
    assert fields["assessment_date"]["value"] is None
    assert actions == []
    assert any("Could not extract any text" in w for w in warnings)


def test_continuation_line_appended_only_after_row_match() -> None:
    text = """
PRIORITY ACTION PLAN
1    High       Replace the damaged final exit door to the yard with a          30/04/2026
               certificated FD30S doorset and self-closer.
APPENDIX A
"""
    _fields, actions, _warnings = parse_fields_from_text(text)
    assert len(actions) == 1
    assert "certificated FD30S" in actions[0].text


@pytest.mark.asyncio
async def test_extract_fail_soft_empty_ocr() -> None:
    class _StubIntelligence:
        async def extract_bytes(self, **kwargs):
            from types import SimpleNamespace

            return SimpleNamespace(
                text="",
                extraction_method="none",
                note=None,
                hard_ocr_failure=False,
                ocr_provider_status="not_configured",
                page_count=None,
            )

    service = FraPas79OcrService(intelligence_service=_StubIntelligence())  # type: ignore[arg-type]
    result = await service.extract(
        content=b"%PDF-1.4 empty",
        filename="empty.pdf",
        content_type="application/pdf",
    )
    assert result.fields["assessment_date"]["value"] is None
    assert result.actions == []
    assert any("Could not extract any text" in w for w in result.warnings)


def test_shared_confidence_reexport() -> None:
    assert CONFIDENCE_HIGH == SHARED_HIGH
    assert CONFIDENCE_MEDIUM == "medium"
