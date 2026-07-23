"""Unit tests for medical assistance + emergency services normalization."""

from src.domain.services.incident_care_fields import (
    care_fields_from_submission,
    derive_emergency_services_called,
    derive_first_aid_given,
    normalize_emergency_services,
    normalize_medical_assistance,
)


def test_normalize_medical_from_excel_yn() -> None:
    assert normalize_medical_assistance("Y") == "first-aider"
    assert normalize_medical_assistance("N") == "none"
    assert normalize_medical_assistance("ambulance") == "ambulance"


def test_normalize_emergency_filters_unknown_and_yn() -> None:
    assert normalize_emergency_services(["police", "fire", "bogus", "Y"]) == ["police", "fire"]
    assert normalize_emergency_services("police,ambulance") == ["police", "ambulance"]


def test_derive_flags() -> None:
    assert derive_first_aid_given("first-aider") is True
    assert derive_first_aid_given("none") is False
    assert derive_emergency_services_called(["police"]) is True
    assert derive_emergency_services_called([]) is False


def test_care_fields_do_not_copy_medical_ambulance_into_emergency() -> None:
    result = care_fields_from_submission({"medical_assistance": "ambulance"})
    assert result["medical_assistance"] == "ambulance"
    assert result["first_aid_given"] is True
    assert result["emergency_services"] is None
    assert result["emergency_services_called"] is False


def test_care_fields_promote_emergency_list() -> None:
    result = care_fields_from_submission(
        {"medical_assistance": "first-aider", "emergency_services": ["police", "ambulance"]}
    )
    assert result["emergency_services"] == ["police", "ambulance"]
    assert result["emergency_services_called"] is True
    assert result["first_aid_given"] is True
