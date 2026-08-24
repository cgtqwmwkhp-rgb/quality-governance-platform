"""Portal intake field limits and contact normalisation (PX-281 backend half)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.routes.employee_portal import (
    PORTAL_COMPLAINANT_PHONE_DB_LENGTH,
    PORTAL_REPORTER_PHONE_MAX_LENGTH,
    PORTAL_RTA_COLLISION_TIME_DB_LENGTH,
    QuickReportCreate,
    build_complaint_portal_fields,
    build_incident_portal_fields,
    build_rta_portal_fields,
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


# --------------------------------------------------------------------------- #
# RTA collision_time is varchar(10) (C-64)
# --------------------------------------------------------------------------- #
#
# The exposure is narrower than free text. ``parse_portal_datetime`` resolves the
# date and time as one ISO string, so an unparseable time ("Approx 8 am") makes the
# whole pair unresolvable and no time is stored at all. What does reach the column
# is an ISO-8601 time longer than ten characters — fractional seconds or a UTC
# offset — which a direct JSON caller or a non-browser client can readily send.
# Unclipped, that raises StringDataRightTruncation and aborts the INSERT, so the
# reporter loses the entire collision report rather than just the time.


def _rta_report(submission: dict) -> QuickReportCreate:
    return QuickReportCreate(
        report_type="rta",
        title="Road Traffic Collision - rear-end - A14",
        description="Rear-ended while stationary on the slip road.",
        location="A14 westbound, junction 52 slip road, Ipswich",
        reporter_name="Pat Reporter",
        reporter_email="pat.reporter@example.com",
        reporter_submission=submission,
    )


@pytest.mark.parametrize(
    "raw_time,expected_utc_hour",
    [
        ("08:30:00.123456", 8),  # microseconds — 15 chars, no offset so read as UTC
        ("08:30:00.123456+01:00", 7),  # microseconds and offset — 21 chars
        ("08:30:00+01:00", 7),  # offset alone — 14 chars
    ],
)
def test_rta_builder_clips_an_over_long_iso_collision_time(raw_time, expected_utc_hour):
    """The report must still be built, with the time clipped rather than the insert lost."""
    assert len(raw_time) > PORTAL_RTA_COLLISION_TIME_DB_LENGTH
    submission = {"accident_date": "2026-07-27", "accident_time": raw_time}

    fields = build_rta_portal_fields(_rta_report(submission), submission, tenant_id=1)

    assert len(fields["collision_time"]) == PORTAL_RTA_COLLISION_TIME_DB_LENGTH
    assert fields["collision_time"] == raw_time[:PORTAL_RTA_COLLISION_TIME_DB_LENGTH]
    # The clip must not cost the rest of the report, and the full instant survives
    # on the typed column — normalised to UTC, so an offset moves the hour.
    assert fields["collision_date"].hour == expected_utc_hour
    assert fields["collision_date"].minute == 30
    assert fields["location"] == "A14 westbound, junction 52 slip road, Ipswich"


@pytest.mark.parametrize("raw_time", ["08:30", "08:30:00"])
def test_rta_builder_leaves_a_fitting_collision_time_exactly_as_submitted(raw_time):
    """What a browser time input emits already fits and must not be altered."""
    submission = {"accident_date": "2026-07-27", "accident_time": raw_time}

    fields = build_rta_portal_fields(_rta_report(submission), submission, tenant_id=1)

    assert fields["collision_time"] == raw_time


def test_rta_builder_stores_no_time_when_the_reporter_gave_none():
    submission = {"accident_date": "2026-07-27"}

    fields = build_rta_portal_fields(_rta_report(submission), submission, tenant_id=1)

    assert fields["collision_time"] is None
