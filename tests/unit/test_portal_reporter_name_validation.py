"""ACT-025: portal missing reporter_name must 422 (never NOT NULL 500)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.routes.employee_portal import (
    QuickReportCreate,
    build_complaint_portal_fields,
    require_portal_display_name,
    resolve_portal_display_name,
)
from src.domain.exceptions import ValidationError
from src.domain.models.complaint import ComplaintPriority
from src.domain.services.portal_service import _resolve_portal_display_name


def test_resolve_anonymous_maps_to_anonymous():
    report = QuickReportCreate(
        report_type="complaint",
        title="Anon complaint title",
        description="Something went wrong for the customer",
        is_anonymous=True,
    )
    assert resolve_portal_display_name(report) == "Anonymous"


def test_resolve_accepts_complainant_name_alias():
    report = QuickReportCreate(
        report_type="complaint",
        title="Named complaint title",
        description="Something went wrong for the customer",
        complainant_name="Pat Complainant",
    )
    assert resolve_portal_display_name(report) == "Pat Complainant"


def test_require_missing_name_raises_422():
    report = QuickReportCreate(
        report_type="near_miss",
        title="Missing name near miss",
        description="Something nearly went wrong on site",
        is_anonymous=False,
    )
    with pytest.raises(HTTPException) as exc_info:
        require_portal_display_name(report)
    assert exc_info.value.status_code == 422


def test_complaint_builder_maps_complainant_name():
    report = QuickReportCreate(
        report_type="complaint",
        title="Complaint with complainant_name only",
        description="Customer unhappy with response time",
        complainant_name="Carol Customer",
        reporter_email="carol@example.com",
    )
    fields = build_complaint_portal_fields(report, ComplaintPriority.MEDIUM, {}, tenant_id=1)
    assert fields["complainant_name"] == "Carol Customer"


def test_portal_service_resolve_requires_name():
    with pytest.raises(ValidationError, match="reporter_name is required"):
        _resolve_portal_display_name({"title": "x"}, is_anonymous=False)
