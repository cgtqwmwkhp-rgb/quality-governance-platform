"""Portal intake field limits and contact normalisation (PX-281 backend half)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.routes.employee_portal import (
    PORTAL_COMPLAINANT_PHONE_DB_LENGTH,
    PORTAL_REPORTER_PHONE_MAX_LENGTH,
    QuickReportCreate,
    build_complaint_portal_fields,
    build_incident_portal_fields,
    clip_portal_location_for_incident,
    clip_portal_phone_for_complaint,
    looks_like_email,
    normalize_portal_contact,
)
from src.domain.models.complaint import ComplaintPriority
from src.domain.models.incident import IncidentSeverity


def test_looks_like_email():
    assert looks_like_email("john.smith@plantexpand.co.uk")
    assert not looks_like_email("+44 7700 900123")
    assert not looks_like_email("ask at reception")


def test_normalize_portal_contact_moves_email_from_phone_field():
    email, phone = normalize_portal_contact(None, "john.smith@plantexpand.co.uk")
    assert email == "john.smith@plantexpand.co.uk"
    assert phone is None


def test_normalize_portal_contact_keeps_distinct_phone_and_email():
    email, phone = normalize_portal_contact("reporter@example.com", "+44 7700 900123")
    assert email == "reporter@example.com"
    assert phone == "+44 7700 900123"


def test_quick_report_create_accepts_long_email_in_reporter_phone():
    long_email = "sam.complainant@averylongcompanyname.co.uk"
    report = QuickReportCreate(
        report_type="complaint",
        title="Customer complaint title",
        description="Something went wrong for the customer",
        reporter_phone=long_email,
        complainant_name="Sam Complainant",
    )
    assert report.reporter_email == long_email
    assert report.reporter_phone is None


def test_quick_report_create_accepts_phone_up_to_near_miss_limit():
    phone = "+" + ("7" * (PORTAL_REPORTER_PHONE_MAX_LENGTH - 1))
    report = QuickReportCreate(
        report_type="near_miss",
        title="Near miss on site today",
        description="Something nearly went wrong on site",
        reporter_name="Pat Reporter",
        reporter_phone=phone,
    )
    assert report.reporter_phone == phone


def test_quick_report_create_rejects_phone_over_api_limit():
    with pytest.raises(ValidationError) as exc_info:
        QuickReportCreate(
            report_type="near_miss",
            title="Near miss on site today",
            description="Something nearly went wrong on site",
            reporter_name="Pat Reporter",
            reporter_phone="+" + ("7" * PORTAL_REPORTER_PHONE_MAX_LENGTH),
        )
    assert "reporter_phone" in str(exc_info.value)


def test_complaint_builder_clips_phone_to_db_column():
    long_phone = "+" + ("7" * 40)
    report = QuickReportCreate(
        report_type="complaint",
        title="Customer complaint title",
        description="Something went wrong for the customer",
        reporter_name="Sam Complainant",
        reporter_phone=long_phone,
    )
    fields = build_complaint_portal_fields(report, ComplaintPriority.MEDIUM, {}, tenant_id=1)
    assert fields["complainant_phone"] == long_phone[:PORTAL_COMPLAINANT_PHONE_DB_LENGTH]
    assert len(fields["complainant_phone"]) == PORTAL_COMPLAINANT_PHONE_DB_LENGTH


def test_incident_builder_clips_location_to_db_column():
    long_location = "Y" * 400
    report = QuickReportCreate(
        report_type="incident",
        title="Incident at depot gate",
        description="Something happened at the depot gate today",
        reporter_name="Alex Reporter",
        location=long_location,
    )
    fields = build_incident_portal_fields(
        report,
        IncidentSeverity.MEDIUM,
        {},
        tenant_id=1,
    )
    assert fields["location"] == clip_portal_location_for_incident(long_location)
    assert len(fields["location"]) == 300


def test_clip_portal_phone_for_complaint_returns_none_for_empty():
    assert clip_portal_phone_for_complaint(None) is None
    assert clip_portal_phone_for_complaint("") is None
