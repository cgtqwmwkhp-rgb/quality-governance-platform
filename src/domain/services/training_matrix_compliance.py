"""Compute training compliance from Atlas Passed + QGP frequency rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

ATLAS_HUB_URL = "https://www.atlas-hub.co.uk/o/98b88f4e-2c3f-44c1-a812-36ea66222c7d/"


@dataclass(frozen=True)
class ComplianceInput:
    course_key: str
    course_display_name: str
    frequency_years: int
    atlas_status: Optional[str]
    passed_on: Optional[date]
    expires_on: Optional[date]


@dataclass(frozen=True)
class ComplianceResult:
    course_key: str
    course_display_name: str
    frequency_years: int
    status: str
    atlas_status: Optional[str]
    passed_on: Optional[date]
    expires_on: Optional[date]
    qgp_due_on: Optional[date]
    expiry_without_passed: bool
    atlas_hub_url: str = ATLAS_HUB_URL


def add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        # 29 Feb → 28 Feb in non-leap target years
        return start.replace(month=2, day=28, year=start.year + years)


def evaluate_compliance(item: ComplianceInput, *, today: Optional[date] = None) -> ComplianceResult:
    today = today or date.today()
    status_l = (item.atlas_status or "").strip().lower()
    expiry_without_passed = bool(item.expires_on and not item.passed_on)

    if status_l == "failed":
        return ComplianceResult(
            course_key=item.course_key,
            course_display_name=item.course_display_name,
            frequency_years=item.frequency_years,
            status="failed",
            atlas_status=item.atlas_status,
            passed_on=item.passed_on,
            expires_on=item.expires_on,
            qgp_due_on=None,
            expiry_without_passed=expiry_without_passed,
        )

    if not item.passed_on:
        # Pending / missing completion — including expiry-without-passed
        st = "pending" if status_l == "pending" or expiry_without_passed else "missing"
        return ComplianceResult(
            course_key=item.course_key,
            course_display_name=item.course_display_name,
            frequency_years=item.frequency_years,
            status=st,
            atlas_status=item.atlas_status,
            passed_on=item.passed_on,
            expires_on=item.expires_on,
            qgp_due_on=None,
            expiry_without_passed=expiry_without_passed,
        )

    due = add_years(item.passed_on, max(1, int(item.frequency_years or 1)))
    if due < today:
        st = "overdue"
    elif due <= today + timedelta(days=30):
        st = "due_soon"
    else:
        st = "compliant"

    return ComplianceResult(
        course_key=item.course_key,
        course_display_name=item.course_display_name,
        frequency_years=item.frequency_years,
        status=st,
        atlas_status=item.atlas_status,
        passed_on=item.passed_on,
        expires_on=item.expires_on,
        qgp_due_on=due,
        expiry_without_passed=expiry_without_passed,
    )


def requirement_matches_engineer(
    *,
    match_department: Optional[str],
    match_role_key: Optional[str],
    engineer_department: Optional[str],
    engineer_job_title: Optional[str],
) -> bool:
    dept_ok = True
    role_ok = True
    if match_department:
        dept_ok = bool(engineer_department and match_department.strip().lower() in engineer_department.strip().lower())
    if match_role_key:
        role_ok = bool(engineer_job_title and match_role_key.strip().lower() in engineer_job_title.strip().lower())
    if not match_department and not match_role_key:
        return False
    return dept_ok and role_ok
