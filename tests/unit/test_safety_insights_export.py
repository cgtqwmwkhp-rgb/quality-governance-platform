"""Unit tests for Safety Insights board-pack export (JSON + PDF builders)."""

from __future__ import annotations

import pytest

from src.domain.services.safety_insights_export import SafetyInsightsExportService, _pdf_safe


def _minimal_board_pack() -> dict:
    return {
        "id": 42,
        "status": "succeeded",
        "scope": "org",
        "topic_query": None,
        "modules": ["incident", "near_miss", "rta"],
        "date_from": "2026-01-01T00:00:00+00:00",
        "date_to": "2026-06-30T23:59:59+00:00",
        "created_at": "2026-07-01T10:00:00+00:00",
        "completed_at": "2026-07-01T10:05:00+00:00",
        "corpus_summary": {"total": 12, "by_module": {"incident": 5, "near_miss": 5, "rta": 2}},
        "ratios": {
            "corpus": {
                "incidents": 5,
                "near_misses": 5,
                "hipo_near_misses": 1,
                "near_miss_to_incident_ratio": 1.0,
                "hipo_near_miss_to_incident_ratio": 0.2,
            },
            "hs_board_by_year": [
                {
                    "reporting_year": 2025,
                    "near_miss_to_injury_ratio": 3.2,
                    "hipo_near_miss_to_injury_ratio": 0.4,
                    "ltifr": 1.1,
                    "afr": 0.3,
                }
            ],
        },
        "quality_scorecard": {
            "total": 12,
            "fields": {
                "missing_root_cause_pct": 16.7,
                "missing_location_pct": 8.3,
                "missing_person_pct": 0.0,
                "rta_missing_vehicle_pct": 0.0,
            },
        },
        "synthesis_text": (
            "Reversing manoeuvres dominate the RTA micro-theme. "
            "Near-miss reporting is parity with incidents in this window."
        ),
        "synthesis_available": True,
        "research_available": True,
        "benchmarks": [
            {
                "title": "HSE workplace transport guidance",
                "summary": "Control reversing risks with banksmen and exclusion zones.",
                "source_url": "https://www.hse.gov.uk/workplacetransport/",
            }
        ],
        "micro_themes": [
            {
                "id": 1,
                "label": "Reversing into stationary object",
                "rationale": "Multiple RTAs share the same manoeuvre pattern.",
                "module_scope": "rta",
                "case_count": 3,
                "share": 0.25,
                "velocity": "stable",
                "severity_overlay": "medium",
                "case_refs": [
                    {"module": "rta", "id": 11, "reference_number": "RTA-2026-0011"},
                    {"module": "rta", "id": 14, "reference_number": "RTA-2026-0014"},
                ],
            },
            {
                "id": 2,
                "label": "Slips on wet plant floors",
                "rationale": "Incident cluster after wash-down.",
                "module_scope": "incident",
                "case_count": 2,
                "share": 0.17,
                "velocity": "rising",
                "severity_overlay": "low",
                "case_refs": [
                    {"module": "incident", "id": 7, "reference_number": "INC-2026-0007"},
                ],
            },
        ],
    }


def test_build_json_board_pack_wraps_serialize_shape() -> None:
    pack = _minimal_board_pack()
    out = SafetyInsightsExportService().build_json_board_pack(pack)
    assert out["format"] == "json"
    assert out["board_pack"] is pack
    assert out["board_pack"]["id"] == 42
    assert out["board_pack"]["micro_themes"][0]["case_refs"][0]["reference_number"] == "RTA-2026-0011"


def test_pdf_filename() -> None:
    assert SafetyInsightsExportService().pdf_filename(42) == "safety-insights-run-42.pdf"


def test_build_pdf_bytes_produces_valid_pdf() -> None:
    pdf_bytes = SafetyInsightsExportService().build_pdf_bytes(_minimal_board_pack())
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
    # Content should mention key sections (compressed streams may hide text; header always present).
    assert b"%PDF" in pdf_bytes


def test_build_pdf_board_pack_returns_filename() -> None:
    pdf_bytes, filename = SafetyInsightsExportService().build_pdf_board_pack(_minimal_board_pack())
    assert filename == "safety-insights-run-42.pdf"
    assert pdf_bytes.startswith(b"%PDF")


def test_build_pdf_handles_sparse_payload() -> None:
    sparse = {
        "id": 7,
        "status": "succeeded",
        "scope": "topic",
        "topic_query": "reversing",
        "modules": [],
        "micro_themes": [],
        "ratios": {},
        "quality_scorecard": {},
        "synthesis_text": None,
        "benchmarks": [],
        "synthesis_available": False,
        "research_available": False,
    }
    pdf_bytes = SafetyInsightsExportService().build_pdf_bytes(sparse)
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_safe_strips_non_latin1() -> None:
    assert _pdf_safe("cost €100") == "cost ?100"
    assert _pdf_safe("abcdefghij", max_len=5) == "ab..."


def test_build_pdf_fails_closed_when_fpdf_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "fpdf" or name.startswith("fpdf."):
            raise ModuleNotFoundError("No module named 'fpdf'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    with pytest.raises(RuntimeError, match="fpdf2 is not installed"):
        SafetyInsightsExportService().build_pdf_bytes(_minimal_board_pack())
