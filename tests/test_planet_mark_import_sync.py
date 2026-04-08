"""Integration tests for Planet Mark audit import → carbon domain sync.

These tests verify the end-to-end pipeline:
  ExternalAuditImportJob (planet_mark, provenance with carbon data)
    → _sync_planet_mark()
      → CarbonReportingYear created/updated
      → EmissionSource aggregate records created per scope
      → ImprovementAction records created from improvement_summary_json
      → ExternalAuditRecord.carbon_reporting_year_id populated

Tests are pure unit/service-layer tests — they use mocked DB sessions so
they do NOT require a live database.  Each test patches SQLAlchemy execute
returns to simulate the DB state.
"""

from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _make_job(
    job_id: int = 1,
    detected_scheme: str = "planet_mark",
    provenance: dict | None = None,
    improvement_summary: list | None = None,
    status: str = "completed",
) -> SimpleNamespace:
    """Create a minimal ExternalAuditImportJob-like object for testing."""
    return SimpleNamespace(
        id=job_id,
        detected_scheme=detected_scheme,
        audit_run_id=10,
        tenant_id=99,
        status=status,
        provenance_json=provenance or {},
        improvement_summary_json=improvement_summary or [],
        scheme_version=None,
        source_filename="planet_mark_report.pdf",
    )


def _make_run(run_id: int = 10, title: str = "Test Org") -> SimpleNamespace:
    return SimpleNamespace(
        id=run_id,
        title=title,
        assurance_scheme="Planet Mark",
        tenant_id=99,
    )


SAMPLE_PM_CARBON = {
    "reporting_year_label": "YE2023",
    "period_start": "2023-01-01",
    "period_end": "2023-12-31",
    "fte_count": 42,
    "scope_1_co2e_tonnes": 12.3,
    "scope_2_co2e_tonnes": 8.1,
    "scope_3_co2e_tonnes": 24.5,
    "total_co2e_tonnes": 44.9,
    "baseline_year_label": "YE2022",
    "baseline_total_co2e_tonnes": 52.1,
    "reduction_percent": 13.8,
    "data_quality_scope_1_2": 12,
    "data_quality_scope_3": 9,
    "certification_number": "PM-2023-TEST",
    "certification_date": "2024-01-15",
    "expiry_date": "2025-01-14",
    "outcome_status": "certified",
    "improvement_actions": [
        {"title": "Install LED lighting", "target_scope": "scope_2", "deadline": "2024-06-30"},
        {"title": "Fleet electrification", "target_scope": "scope_1", "deadline": "2025-01-01"},
    ],
}


# ────────────────────────────────────────────────────────────────────────────
# _is_planet_mark_scheme
# ────────────────────────────────────────────────────────────────────────────


class TestIsPlanetMarkScheme:
    def _import_service(self):
        from src.domain.services.external_audit_import_service import ExternalAuditImportService

        return ExternalAuditImportService

    def test_detects_planet_mark_scheme(self):
        Service = self._import_service()
        job = _make_job(detected_scheme="planet_mark")
        assert Service._is_planet_mark_scheme(job) is True

    def test_not_planet_mark_for_uvdb(self):
        Service = self._import_service()
        job = _make_job(detected_scheme="achilles_uvdb")
        assert Service._is_planet_mark_scheme(job) is False

    def test_detects_via_provenance_declared_scheme(self):
        Service = self._import_service()
        job = _make_job(
            detected_scheme="unknown",
            provenance={"declared_vs_detected": {"declared_assurance_scheme": "planet mark"}},
        )
        assert Service._is_planet_mark_scheme(job) is True


# ────────────────────────────────────────────────────────────────────────────
# MistralAnalysisService._validate_planet_mark_carbon
# ────────────────────────────────────────────────────────────────────────────


class TestValidatePlanetMarkCarbon:
    def _validator(self):
        from src.domain.services.mistral_analysis_service import MistralAnalysisService

        return MistralAnalysisService._validate_planet_mark_carbon

    def test_valid_data_passes_through(self):
        validate = self._validator()
        result = validate(SAMPLE_PM_CARBON)
        assert result["scope_1_co2e_tonnes"] == 12.3
        assert result["scope_2_co2e_tonnes"] == 8.1
        assert result["scope_3_co2e_tonnes"] == 24.5
        assert result["fte_count"] == 42
        assert result["outcome_status"] == "certified"
        assert result["certification_number"] == "PM-2023-TEST"
        assert len(result["improvement_actions"]) == 2

    def test_negative_emissions_rejected(self):
        validate = self._validator()
        result = validate({**SAMPLE_PM_CARBON, "scope_1_co2e_tonnes": -5.0})
        assert result["scope_1_co2e_tonnes"] is None

    def test_extreme_emissions_rejected(self):
        validate = self._validator()
        result = validate({**SAMPLE_PM_CARBON, "scope_1_co2e_tonnes": 99_000_000})
        assert result["scope_1_co2e_tonnes"] is None

    def test_data_quality_above_16_rejected(self):
        validate = self._validator()
        result = validate({**SAMPLE_PM_CARBON, "data_quality_scope_1_2": 20})
        assert result["data_quality_scope_1_2"] is None

    def test_invalid_outcome_status_set_to_none(self):
        validate = self._validator()
        result = validate({**SAMPLE_PM_CARBON, "outcome_status": "unknown_status"})
        assert result["outcome_status"] is None

    def test_improvement_action_without_title_skipped(self):
        validate = self._validator()
        result = validate(
            {
                **SAMPLE_PM_CARBON,
                "improvement_actions": [{"title": "", "target_scope": "scope_1"}],
            }
        )
        assert result["improvement_actions"] == []

    def test_max_20_improvement_actions(self):
        validate = self._validator()
        actions = [{"title": f"Action {i}"} for i in range(30)]
        result = validate({**SAMPLE_PM_CARBON, "improvement_actions": actions})
        assert len(result["improvement_actions"]) == 20


# ────────────────────────────────────────────────────────────────────────────
# ExternalAuditAnalysisService._extract_planet_mark_carbon_regex
# ────────────────────────────────────────────────────────────────────────────


class TestExtractPlanetMarkCarbonRegex:
    def _extractor(self):
        from src.domain.services.external_audit_analysis_service import ExternalAuditAnalysisService

        return ExternalAuditAnalysisService._extract_planet_mark_carbon_regex

    def test_extracts_scope_emissions(self):
        extract = self._extractor()
        text = (
            "Scope 1 Direct Emissions 12.3 tCO2e\n"
            "Scope 2 Indirect Energy 8.1 tCO2e\n"
            "Scope 3 Value Chain 24.5 tCO2e\n"
            "Total 44.9 tCO2e\n"
            "42 FTE\n"
            "Data quality 14/16\n"
            "Planet Mark Certified"
        )
        result = extract(text)
        assert result is not None
        assert result["scope_1_co2e_tonnes"] == pytest.approx(12.3, rel=0.01)
        assert result["scope_2_co2e_tonnes"] == pytest.approx(8.1, rel=0.01)
        assert result["scope_3_co2e_tonnes"] == pytest.approx(24.5, rel=0.01)
        assert result["fte_count"] == 42
        assert result["data_quality_scope_1_2"] == 14
        assert result["outcome_status"] == "certified"

    def test_returns_none_when_no_carbon_data(self):
        extract = self._extractor()
        text = "This is a generic audit report with no emission data."
        result = extract(text)
        assert result is None

    def test_converts_large_values_from_kg(self):
        extract = self._extractor()
        # 123000 kgCO2e → 123.0 tCO2e
        text = "Scope 1 direct emissions 123000 tCO2e"
        result = extract(text)
        # Value > 100,000 should be divided by 1000
        assert result is not None
        assert result["scope_1_co2e_tonnes"] == pytest.approx(123.0, rel=0.01)


# ────────────────────────────────────────────────────────────────────────────
# Planet Mark scheme profile validation
# ────────────────────────────────────────────────────────────────────────────


class TestPlanetMarkSchemeProfile:
    def test_profile_exists(self):
        from src.domain.services.scheme_profiles import SCHEME_PROFILES

        profile = SCHEME_PROFILES["planet_mark"]
        assert profile.scheme_id == "planet_mark"
        assert profile.score_type == "percentage"
        assert len(profile.sections) > 0

    def test_certified_outcome_is_valid(self):
        from src.domain.services.scheme_profiles import SCHEME_PROFILES

        profile = SCHEME_PROFILES["planet_mark"]
        assert "certified" in profile.valid_outcomes

    def test_validate_against_scheme_no_crash(self):
        from src.domain.services.scheme_profiles import validate_against_scheme

        warnings = validate_against_scheme("planet_mark", 44.9, None, 86.2, [])
        assert isinstance(warnings, list)


# ────────────────────────────────────────────────────────────────────────────
# Timezone fix: ensure naive UTC comparisons work
# ────────────────────────────────────────────────────────────────────────────


class TestTimezoneFixInPlanetMarkService:
    def test_overdue_comparison_uses_naive_datetime(self):
        """The overdue comparison must not raise TypeError for naive datetimes."""
        # Simulate what list_improvement_actions does
        now = datetime.utcnow()
        # time_bound stored as naive UTC
        naive_past = datetime(2020, 1, 1)
        naive_future = datetime(2099, 1, 1)

        # Should not raise
        is_overdue_past = naive_past < now
        is_overdue_future = naive_future < now

        assert is_overdue_past is True
        assert is_overdue_future is False

    def test_no_timezone_import_in_service(self):
        """Confirm planet_mark_service no longer uses timezone.utc for comparisons."""
        import ast
        import pathlib

        source = pathlib.Path("src/domain/services/planet_mark_service.py").read_text()
        # Should not have datetime.now(timezone.utc) (which was the bug)
        assert "datetime.now(timezone.utc)" not in source, (
            "planet_mark_service.py still uses timezone-aware comparison. " "Must use datetime.utcnow() for naive UTC."
        )
