"""Unit tests for KRICalculationService (D15 coverage uplift)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.domain.services.kri_calculation_service import KRICalculationService


class TestApplySifAssessment:
    """Tests for KRICalculationService.apply_sif_assessment."""

    def _make_incident(self) -> SimpleNamespace:
        return SimpleNamespace(
            is_sif=None,
            is_psif=None,
            sif_classification=None,
            sif_assessment_date=None,
            sif_assessed_by_id=None,
            sif_rationale=None,
            life_altering_potential=None,
            precursor_events=None,
            control_failures=None,
        )

    def _make_assessment(self, **kwargs) -> SimpleNamespace:
        defaults = dict(
            is_sif=True,
            is_psif=False,
            sif_classification="SIF",
            sif_rationale="Fatal energy present",
            life_altering_potential=True,
            precursor_events="Near-miss x3",
            control_failures="Lock-out not followed",
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_applies_sif_fields_to_incident(self) -> None:
        incident = self._make_incident()
        assessment = self._make_assessment()
        before = datetime.now(timezone.utc)

        KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=42)

        assert incident.is_sif is True
        assert incident.is_psif is False
        assert incident.sif_classification == "SIF"
        assert incident.sif_assessed_by_id == 42
        assert incident.sif_rationale == "Fatal energy present"
        assert incident.life_altering_potential is True
        assert incident.precursor_events == "Near-miss x3"
        assert incident.control_failures == "Lock-out not followed"
        assert incident.sif_assessment_date >= before

    def test_psif_classification_applied(self) -> None:
        incident = self._make_incident()
        assessment = self._make_assessment(is_sif=False, is_psif=True, sif_classification="pSIF")

        KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=99)

        assert incident.is_sif is False
        assert incident.is_psif is True
        assert incident.sif_classification == "pSIF"

    def test_assessment_date_is_utc(self) -> None:
        incident = self._make_incident()
        assessment = self._make_assessment()

        KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

        assert incident.sif_assessment_date.tzinfo is not None

    def test_none_values_in_assessment_are_applied(self) -> None:
        incident = self._make_incident()
        assessment = self._make_assessment(precursor_events=None, control_failures=None)

        KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=7)

        assert incident.precursor_events is None
        assert incident.control_failures is None
