"""Incident create-from-record must copy the same field set near-miss already maps."""

from __future__ import annotations

from types import SimpleNamespace

from src.domain.models.incident import IncidentSeverity
from src.domain.models.investigation import AssignedEntityType
from src.domain.services.investigation_service import InvestigationService


def test_incident_mapping_copies_people_actions_severity_and_injury() -> None:
    record = SimpleNamespace(
        reference_number="INC-2026-0042",
        incident_date=None,
        location="Depot yard",
        description="Forklift struck a stillage",
        people_involved="Alex Driver, yard marshal",
        witnesses="Sam Banks",
        severity=IncidentSeverity.HIGH,
        department="Plant",
        is_injury=True,
        body_parts=["hand", "wrist"],
        is_lti=True,
        days_lost=3,
        is_minor_injury=False,
        immediate_actions="Isolated the machine; first aider attended",
        first_aid_given=True,
        emergency_services_called=False,
        medical_assistance="first_aider",
    )

    data, log, level = InvestigationService.map_source_to_investigation(
        record, AssignedEntityType.REPORTING_INCIDENT
    )

    details = data["sections"]["section_1_details"]
    actions = data["sections"]["section_2_immediate_actions"]

    assert details["persons_involved"] == "Alex Driver, yard marshal"
    assert details["witnesses"] == "Sam Banks"
    assert details["severity"] == "high"
    assert details["department"] == "Plant"
    assert details["is_injury"] is True
    assert details["body_parts"] == ["hand", "wrist"]
    assert details["is_lti"] is True
    assert details["days_lost"] == 3
    assert actions["actions_taken"] == "Isolated the machine; first aider attended"
    assert actions["first_aid_given"] is True
    assert actions["emergency_services_called"] is False
    assert str(level.value if hasattr(level, "value") else level) == "high"
    assert any(entry["source_field"] == "people_involved" and entry["result"] != "FALLBACK" for entry in log)


def test_incident_mapping_still_copies_the_original_four_fields() -> None:
    record = SimpleNamespace(
        reference_number="INC-1",
        incident_date=None,
        location="A1",
        description="Collision",
        people_involved=None,
        witnesses=None,
        severity=None,
        department=None,
        is_injury=False,
        body_parts=None,
        is_lti=False,
        days_lost=None,
        is_minor_injury=False,
        immediate_actions=None,
        first_aid_given=False,
        emergency_services_called=False,
        medical_assistance=None,
    )

    data, _log, _level = InvestigationService.map_source_to_investigation(
        record, AssignedEntityType.REPORTING_INCIDENT
    )
    details = data["sections"]["section_1_details"]

    assert details["reference_number"] == "INC-1"
    assert details["location"] == "A1"
    assert details["description"] == "Collision"
    assert details["persons_involved"] is None
    assert details["witnesses"] is None
