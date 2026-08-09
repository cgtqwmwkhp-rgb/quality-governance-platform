"""RequirementResponse.owner_name is an additive schedule display field."""

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
        owner_id=99,
        is_active=True,
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at=None,
        template=SimpleNamespace(template_key=ComplianceScheduleService.FRA_TEMPLATE_KEY),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_requirement_response_owner_name_defaults_to_none() -> None:
    resp = _requirement_response(_row())
    assert resp.owner_id == 99
    assert resp.owner_name is None


def test_requirement_response_includes_resolved_owner_name() -> None:
    resp = _requirement_response(_row(), owner_name="Jamie Uncle")
    assert resp.owner_id == 99
    assert resp.owner_name == "Jamie Uncle"


def test_requirement_response_owner_name_none_when_unassigned() -> None:
    resp = _requirement_response(_row(owner_id=None), owner_name=None)
    assert resp.owner_id is None
    assert resp.owner_name is None
