"""Assign-owner must survive operational-assess / notify side-effect failures."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.incidents import _trigger_operational_standards_assess, update_incident
from src.api.schemas.incident import IncidentUpdate


@asynccontextmanager
async def _nested_ok():
    yield


@pytest.mark.asyncio
async def test_update_incident_owner_survives_assess_failure() -> None:
    """Assess failure must not 500 assign — nested isolation + swallowed errors."""
    incident = SimpleNamespace(
        id=63,
        reference_number="SAMPLE-INC-005",
        title="Security Access Review",
        description="Test",
        tenant_id=None,
        owner_id=None,
    )
    updated = SimpleNamespace(
        id=63,
        reference_number="SAMPLE-INC-005",
        title="Security Access Review",
        description="Test",
        tenant_id=None,
        owner_id=42,
    )
    db = SimpleNamespace(
        begin_nested=_nested_ok,
        refresh=AsyncMock(),
    )
    service = SimpleNamespace(
        get_incident=AsyncMock(return_value=incident),
        update_incident=AsyncMock(return_value=updated),
    )
    current_user = SimpleNamespace(id=7, tenant_id=11, is_superuser=False)

    with (
        patch("src.api.routes.incidents.IncidentService", return_value=service),
        patch("src.api.routes.incidents._validate_case_owner", new_callable=AsyncMock),
        patch(
            "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ai_decision_logs tenant_id null"),
        ),
        patch("src.api.routes.incidents._notify_case_owner_assignment", new_callable=AsyncMock) as notify,
    ):
        result = await update_incident(
            incident_id=63,
            incident_data=IncidentUpdate(owner_id=42),
            db=db,
            current_user=current_user,
            request_id="req-assign",
        )

    assert result.owner_id == 42
    notify.assert_awaited_once()
    service.update_incident.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_assess_uses_user_tenant_when_incident_tenant_missing() -> None:
    incident = SimpleNamespace(id=63, title="t", description="d", tenant_id=None)
    current_user = SimpleNamespace(id=7, tenant_id=11)
    assess = AsyncMock()
    db = MagicMock()
    db.begin_nested = lambda: _nested_ok()

    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        assess,
    ):
        await _trigger_operational_standards_assess(db, incident, current_user)

    assess.assert_awaited_once()
    assert assess.await_args.kwargs["tenant_id"] == 11
