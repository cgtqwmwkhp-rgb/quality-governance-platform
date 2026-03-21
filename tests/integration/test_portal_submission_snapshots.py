"""Regression tests for portal submission field preservation helpers."""

from src.api.routes.employee_portal import (
    QuickReportCreate,
    build_complaint_portal_fields,
    build_incident_portal_fields,
    build_rta_portal_fields,
)
from src.domain.models.complaint import ComplaintPriority
from src.domain.models.incident import IncidentSeverity
from src.domain.models.rta import RTASeverity


def test_incident_submission_helper_preserves_snapshot_and_triage_fields():
    report = QuickReportCreate(
        report_type="incident",
        title="Incident with structured intake",
        description="Worker slip on entrance steps",
        severity="high",
        location="North gate",
        department="Facilities",
        reporter_name="Alice Reporter",
        reporter_email="alice@example.com",
        reporter_submission={
            "person_name": "Bob Worker",
            "person_role": "Cleaner",
            "incident_date": "2026-03-15",
            "incident_time": "09:45",
            "witness_names": "Jane Witness",
            "medical_assistance": "ambulance",
        },
    )

    fields = build_incident_portal_fields(
        report,
        IncidentSeverity.HIGH,
        report.reporter_submission or {},
    )

    assert fields["reporter_submission"]["person_name"] == "Bob Worker"
    assert fields["people_involved"] == "Bob Worker"
    assert fields["witnesses"] == "Jane Witness"
    assert fields["first_aid_given"] is True
    assert fields["emergency_services_called"] is True
    assert fields["incident_date"].date().isoformat() == "2026-03-15"


def test_complaint_submission_helper_preserves_snapshot_and_owner_context():
    report = QuickReportCreate(
        report_type="complaint",
        title="Complaint with reporter context",
        description="Customer unhappy with response time",
        severity="medium",
        department="Responsive Repairs",
        reporter_name="Carol Customer",
        reporter_email="carol@example.com",
        reporter_phone="07000000000",
        reporter_submission={
            "contract": "responsive_repairs",
            "complainant_name": "Carol Customer",
            "complainant_role": "Resident",
            "complainant_contact": "07000000000",
            "location": "Block A",
        },
    )

    fields = build_complaint_portal_fields(
        report,
        ComplaintPriority.MEDIUM,
        report.reporter_submission or {},
    )

    assert fields["department"] == "Responsive Repairs"
    assert fields["reporter_submission"]["complainant_role"] == "Resident"
    assert fields["complainant_name"] == "Carol Customer"
    assert fields["complainant_phone"] == "07000000000"


def test_rta_submission_helper_preserves_snapshot_and_operational_brief():
    report = QuickReportCreate(
        report_type="rta",
        title="Structured collision",
        description="Vehicle struck at junction",
        severity="high",
        location="A10 / B2 junction",
        reporter_name="Dan Driver",
        reporter_email="dan@example.com",
        reporter_submission={
            "employee_name": "Dan Driver",
            "pe_vehicle": "other",
            "pe_vehicle_other": "PE12345",
            "accident_date": "2026-03-16",
            "accident_time": "18:05",
            "vehicle_count": 2,
            "weather": "Rain",
            "road_condition": "Wet",
            "damage_description": "Rear quarter panel damage",
            "witness_details": "John Witness 07123456789",
            "third_parties": [
                {
                    "vehicle_reg": "AB12 CDE",
                    "name": "Third Party Driver",
                    "phone": "07999999999",
                }
            ],
            "police_ref": "POL-42",
            "has_dashcam": True,
            "has_cctv": True,
            "photos": {"count": 3},
        },
    )

    fields = build_rta_portal_fields(
        report,
        RTASeverity.SERIOUS_INJURY,
        report.reporter_submission or {},
    )

    assert fields["reporter_submission"]["employee_name"] == "Dan Driver"
    assert fields["company_vehicle_registration"] == "PE12345"
    assert fields["vehicles_involved_count"] == 3
    assert fields["police_reference"] == "POL-42"
    assert fields["cctv_available"] is True
    assert fields["dashcam_footage_available"] is True
    assert fields["collision_date"].date().isoformat() == "2026-03-16"
    assert fields["third_parties"]["parties"][0]["vehicle_reg"] == "AB12 CDE"
