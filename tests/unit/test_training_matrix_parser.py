"""Unit tests for Atlas training matrix CSV parser + compliance engine."""

from datetime import date

from src.domain.services.training_matrix_compliance import (
    ComplianceInput,
    evaluate_compliance,
    requirement_matches_engineer,
)
from src.domain.services.training_matrix_parser import parse_training_matrix_csv

SAMPLE_CSV = """Training matrix ,,
,,Asbestos Awareness,,,Fire Safety Awareness,,,Manual Handling
Trainee,Department,Status,Passed,Expiry,Status,Passed,Expiry,Status,Passed,Expiry
Aaron Smith,Mobile Engineers,Passed,02/12/2022,21/11/2025,Pending,,30/12/2025,Passed,27/12/2024,27/12/2026
Aidan Binley,Workshop,Passed,11/05/2026,11/05/2027,,, ,Passed,07/05/2025,07/05/2027
"""


def test_parse_training_matrix_csv_shape():
    parsed = parse_training_matrix_csv(SAMPLE_CSV)
    assert parsed.courses == ["Asbestos Awareness", "Fire Safety Awareness", "Manual Handling"]
    assert len(parsed.people) == 2
    assert parsed.people[0].atlas_name == "Aaron Smith"
    assert parsed.people[0].department == "Mobile Engineers"
    assert parsed.expiry_without_passed_count == 1
    aaron_fire = next(c for c in parsed.people[0].cells if c.course_key == "fire_safety_awareness")
    assert aaron_fire.atlas_status == "Pending"
    assert aaron_fire.passed_on is None
    assert aaron_fire.expires_on == date(2025, 12, 30)


def test_compliance_uses_passed_plus_frequency():
    result = evaluate_compliance(
        ComplianceInput(
            course_key="asbestos_awareness",
            course_display_name="Asbestos Awareness",
            frequency_years=3,
            atlas_status="Passed",
            passed_on=date(2022, 12, 2),
            expires_on=date(2023, 12, 2),  # Atlas 12m — advisory only
        ),
        today=date(2026, 7, 20),
    )
    assert result.qgp_due_on == date(2025, 12, 2)
    assert result.status == "overdue"


def test_compliance_pending_expiry_without_passed():
    result = evaluate_compliance(
        ComplianceInput(
            course_key="fire_safety_awareness",
            course_display_name="Fire Safety Awareness",
            frequency_years=1,
            atlas_status="Pending",
            passed_on=None,
            expires_on=date(2025, 12, 30),
        ),
        today=date(2026, 7, 20),
    )
    assert result.status == "pending"
    assert result.expiry_without_passed is True
    assert result.qgp_due_on is None


def test_requirement_match_department():
    assert requirement_matches_engineer(
        match_department="Mobile Engineers",
        match_role_key=None,
        engineer_department="Mobile Engineers",
        engineer_job_title="Technician",
    )
    assert not requirement_matches_engineer(
        match_department="Workshop",
        match_role_key=None,
        engineer_department="Mobile Engineers",
        engineer_job_title="Technician",
    )


def test_parse_dedupes_duplicate_trainee_rows():
    csv_dup = SAMPLE_CSV + "Aaron Smith,Mobile Engineers,Passed,02/12/2023,21/11/2026,,,,,\n"
    parsed = parse_training_matrix_csv(csv_dup)
    assert len(parsed.people) == 2
    aaron = next(p for p in parsed.people if p.atlas_name == "Aaron Smith")
    asbestos = next(c for c in aaron.cells if c.course_key == "asbestos_awareness")
    assert asbestos.passed_on == date(2023, 12, 2)
