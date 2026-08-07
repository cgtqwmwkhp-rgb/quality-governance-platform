"""Slice 3: RequirementResponse.fra_ocr_eligible mirrors backend FRA gate."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from src.api.routes.compliance_schedule import _requirement_response
from src.domain.services.compliance_schedule_service import ComplianceScheduleService


def _row(**overrides):
    base = dict(
        id=7,
        external_id="ext-7",
        tenant_id=1,
        reference_number="CSR-1",
        template_id=3,
        location_id=12,
        title="FRA",
        taxonomy_id="03.02",
        description=None,
        regulatory_basis=None,
        regulatory_standard_id=None,
        regulatory_clause_id=None,
        frequency_months=12,
        frequency_days=None,
        anchor="schedule",
        statutory=True,
        next_due_date=date(2026, 9, 1),
        last_completed_at=None,
        owner_id=None,
        is_active=True,
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at=None,
        template=SimpleNamespace(template_key=ComplianceScheduleService.FRA_TEMPLATE_KEY),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_requirement_response_template_keyed_non_03_01_is_eligible() -> None:
    resp = _requirement_response(_row(taxonomy_id="03.02"))
    assert resp.fra_ocr_eligible is True


def test_requirement_response_custom_03_01_is_eligible() -> None:
    resp = _requirement_response(
        _row(template_id=None, template=None, taxonomy_id="03.01"),
    )
    assert resp.fra_ocr_eligible is True


def test_requirement_response_inactive_or_org_wide_not_eligible() -> None:
    assert _requirement_response(_row(is_active=False)).fra_ocr_eligible is False
    assert _requirement_response(_row(location_id=None)).fra_ocr_eligible is False


def test_requirement_response_non_fra_not_eligible() -> None:
    resp = _requirement_response(
        _row(
            taxonomy_id="01.01",
            template=SimpleNamespace(template_key="fire_drill_evacuation"),
        )
    )
    assert resp.fra_ocr_eligible is False
