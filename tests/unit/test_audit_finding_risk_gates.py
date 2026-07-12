"""Unit tests for inspection finding → organisational risk gates."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.audit_service import AuditService


def _service() -> AuditService:
    return AuditService(MagicMock())


@pytest.mark.asyncio
async def test_positive_finding_does_not_auto_create_org_risk():
    service = _service()
    run = SimpleNamespace(
        tenant_id=1,
        reference_number="AUD-1",
        assigned_to_id=None,
        assurance_scheme="ISO",
        location=None,
        external_reference=None,
    )
    finding = SimpleNamespace(
        id=10,
        reference_number="AF-10",
        title="Great practice",
        description="Positive",
        severity="low",
        finding_type="positive_practice",
        risk_ids_json=None,
        corrective_action_required=False,
    )

    risk = await service._ensure_risk_for_finding(
        run=run,
        finding=finding,
        action=None,
        actor_user_id=1,
    )
    assert risk is None


@pytest.mark.asyncio
async def test_nonconformity_still_auto_creates_when_severity_eligible(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    run = SimpleNamespace(
        tenant_id=1,
        reference_number="AUD-1",
        assigned_to_id=None,
        assurance_scheme="ISO",
        location=None,
        external_reference=None,
    )
    finding = SimpleNamespace(
        id=11,
        reference_number="AF-11",
        title="NC",
        description="Failed",
        severity="high",
        finding_type="nonconformity",
        risk_ids_json=None,
        corrective_action_required=True,
    )

    existing = SimpleNamespace(
        id=99,
        linked_audits=[],
        linked_actions=[],
    )

    class _Result:
        def scalars(self):
            return self

        def first(self):
            return existing

    service.db.execute = AsyncMock(return_value=_Result())  # type: ignore[method-assign]

    risk = await service._ensure_risk_for_finding(
        run=run,
        finding=finding,
        action=None,
        actor_user_id=1,
    )
    assert risk is existing
    assert finding.risk_ids_json == [99]


@pytest.mark.asyncio
async def test_force_flag_allows_positive_finding_risk(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    run = SimpleNamespace(
        tenant_id=1,
        reference_number="AUD-1",
        assigned_to_id=None,
        assurance_scheme="ISO",
        location=None,
        external_reference=None,
    )
    finding = SimpleNamespace(
        id=12,
        reference_number="AF-12",
        title="Positive but significant",
        description="Needs register visibility",
        severity="medium",
        finding_type="positive",
        risk_ids_json=None,
        corrective_action_required=False,
    )

    existing = SimpleNamespace(id=77, linked_audits=[], linked_actions=[])

    class _Result:
        def scalars(self):
            return self

        def first(self):
            return existing

    service.db.execute = AsyncMock(return_value=_Result())  # type: ignore[method-assign]

    risk = await service._ensure_risk_for_finding(
        run=run,
        finding=finding,
        action=None,
        actor_user_id=1,
        force_flag=True,
    )
    assert risk is existing
