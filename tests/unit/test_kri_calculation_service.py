"""Unit tests for KRI Calculation Service - can run standalone."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from src.domain.services.kri_calculation_service import KRICalculationService

    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_incident(**overrides):
    """Create a mock incident object with SIF-related attributes."""
    incident = MagicMock()
    incident.is_sif = None
    incident.is_psif = None
    incident.sif_classification = None
    incident.sif_assessment_date = None
    incident.sif_assessed_by_id = None
    incident.sif_rationale = None
    incident.life_altering_potential = None
    incident.precursor_events = None
    incident.control_failures = None
    for key, value in overrides.items():
        setattr(incident, key, value)
    return incident


def _mock_assessment(
    is_sif=True,
    is_psif=False,
    sif_classification="confirmed",
    sif_rationale="Fall from height",
    life_altering_potential=True,
    precursor_events=None,
    control_failures=None,
):
    """Create a mock SIF assessment object."""
    assessment = MagicMock()
    assessment.is_sif = is_sif
    assessment.is_psif = is_psif
    assessment.sif_classification = sif_classification
    assessment.sif_rationale = sif_rationale
    assessment.life_altering_potential = life_altering_potential
    assessment.precursor_events = precursor_events if precursor_events is not None else ["inadequate_guardrail"]
    assessment.control_failures = control_failures if control_failures is not None else ["missing_harness"]
    return assessment


# ---------------------------------------------------------------------------
# apply_sif_assessment — basic application
# ---------------------------------------------------------------------------


def test_apply_sif_assessment_sets_is_sif():
    """apply_sif_assessment copies is_sif from assessment to incident."""
    incident = _mock_incident()
    assessment = _mock_assessment(is_sif=True)

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=42)

    assert incident.is_sif is True


def test_apply_sif_assessment_sets_is_psif():
    """apply_sif_assessment copies is_psif from assessment to incident."""
    incident = _mock_incident()
    assessment = _mock_assessment(is_psif=True)

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=7)

    assert incident.is_psif is True


def test_apply_sif_assessment_sets_classification():
    """SIF classification is transferred to the incident."""
    incident = _mock_incident()
    assessment = _mock_assessment(sif_classification="potential")

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.sif_classification == "potential"


def test_apply_sif_assessment_sets_rationale():
    """SIF rationale text is transferred to the incident."""
    incident = _mock_incident()
    assessment = _mock_assessment(sif_rationale="Electrical contact with live wire")

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.sif_rationale == "Electrical contact with live wire"


def test_apply_sif_assessment_sets_assessed_by_id():
    """The assessor user ID is recorded on the incident."""
    incident = _mock_incident()
    assessment = _mock_assessment()

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=99)

    assert incident.sif_assessed_by_id == 99


def test_apply_sif_assessment_sets_assessment_date():
    """An assessment date is stamped on the incident."""
    incident = _mock_incident()
    assessment = _mock_assessment()

    before = datetime.now(timezone.utc)
    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)
    after = datetime.now(timezone.utc)

    assert before <= incident.sif_assessment_date <= after


def test_apply_sif_assessment_sets_life_altering_potential():
    """Life-altering potential flag is transferred."""
    incident = _mock_incident()
    assessment = _mock_assessment(life_altering_potential=True)

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.life_altering_potential is True


def test_apply_sif_assessment_sets_precursor_events():
    """Precursor events list is transferred."""
    events = ["near_miss", "equipment_failure"]
    incident = _mock_incident()
    assessment = _mock_assessment(precursor_events=events)

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.precursor_events == events


def test_apply_sif_assessment_sets_control_failures():
    """Control failures list is transferred."""
    failures = ["lockout_bypass", "no_ppe"]
    incident = _mock_incident()
    assessment = _mock_assessment(control_failures=failures)

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.control_failures == failures


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_apply_sif_assessment_non_sif_incident():
    """A non-SIF assessment correctly sets is_sif=False."""
    incident = _mock_incident()
    assessment = _mock_assessment(
        is_sif=False,
        is_psif=False,
        sif_classification="not_applicable",
        life_altering_potential=False,
    )

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.is_sif is False
    assert incident.is_psif is False
    assert incident.sif_classification == "not_applicable"
    assert incident.life_altering_potential is False


def test_apply_sif_assessment_psif_only():
    """A pSIF (potential SIF) assessment sets is_psif=True and is_sif=False."""
    incident = _mock_incident()
    assessment = _mock_assessment(
        is_sif=False,
        is_psif=True,
        sif_classification="potential",
    )

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.is_sif is False
    assert incident.is_psif is True
    assert incident.sif_classification == "potential"


def test_apply_sif_assessment_empty_control_failures():
    """Empty control failures list is handled correctly."""
    incident = _mock_incident()
    assessment = _mock_assessment(control_failures=[])

    KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert incident.control_failures == []


def test_apply_sif_assessment_mutates_incident_in_place():
    """apply_sif_assessment returns None — it mutates in place."""
    incident = _mock_incident()
    assessment = _mock_assessment()

    result = KRICalculationService.apply_sif_assessment(incident, assessment, assessed_by_id=1)

    assert result is None


if __name__ == "__main__":
    print("=" * 60)
    print("KRI CALCULATION SERVICE UNIT TESTS")
    print("=" * 60)

    test_apply_sif_assessment_sets_is_sif()
    print("✓ sets is_sif")
    test_apply_sif_assessment_sets_is_psif()
    print("✓ sets is_psif")
    test_apply_sif_assessment_sets_classification()
    print("✓ sets classification")
    test_apply_sif_assessment_sets_rationale()
    print("✓ sets rationale")
    test_apply_sif_assessment_sets_assessed_by_id()
    print("✓ sets assessed_by_id")
    test_apply_sif_assessment_sets_assessment_date()
    print("✓ sets assessment date")
    test_apply_sif_assessment_sets_life_altering_potential()
    print("✓ sets life_altering_potential")
    test_apply_sif_assessment_sets_precursor_events()
    print("✓ sets precursor_events")
    test_apply_sif_assessment_sets_control_failures()
    print("✓ sets control_failures")
    test_apply_sif_assessment_non_sif_incident()
    print("✓ non-SIF incident")
    test_apply_sif_assessment_psif_only()
    print("✓ pSIF only")
    test_apply_sif_assessment_empty_control_failures()
    print("✓ empty control failures")
    test_apply_sif_assessment_mutates_incident_in_place()
    print("✓ mutates in place")

    print()
    print("=" * 60)
    print("ALL KRI CALCULATION SERVICE TESTS PASSED ✅")
    print("=" * 60)
