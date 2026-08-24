"""PX-426: second POST for the same audit finding returns the existing CAPA."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.routes.actions import ActionCreate, ActionResponse, create_action, get_audit_finding_capa_for_tenant
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType


def _unique_source_error() -> IntegrityError:
    return IntegrityError(
        "INSERT INTO capa_actions",
        {},
        Exception('duplicate key value violates unique constraint "uq_capa_actions_tenant_audit_finding_source"'),
    )


@pytest.mark.asyncio
async def test_get_audit_finding_capa_for_tenant_queries_unique_key() -> None:
    existing = SimpleNamespace(id=74, source_id=203)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = existing
    db = SimpleNamespace(execute=AsyncMock(return_value=execute_result))

    found = await get_audit_finding_capa_for_tenant(db, tenant_id=1, source_id=203)

    assert found is existing
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_action_returns_existing_capa_on_finding_unique() -> None:
    finding = SimpleNamespace(id=203, run_id=84, reference_number="FND-2026-0203", title="NC")
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [finding]

    db = SimpleNamespace(
        execute=AsyncMock(return_value=execute_result),
        add=MagicMock(),
        commit=AsyncMock(side_effect=_unique_source_error()),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )
    current_user = SimpleNamespace(id=7, tenant_id=1)

    existing = CAPAAction(
        tenant_id=1,
        reference_number="CAPA-2026-0010",
        title="Existing CAPA",
        description="Already raised",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.AUDIT_FINDING,
        source_id=203,
        created_by_id=7,
        assigned_to_id=9,
    )
    existing.id = 74
    existing.created_at = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)

    existing_response = ActionResponse(
        id=74,
        reference_number="CAPA-2026-0010",
        title="Existing CAPA",
        description="Already raised",
        action_type="corrective",
        priority="medium",
        status="open",
        display_status="open",
        action_key="capa:74",
        source_type="audit_finding",
        source_id=203,
        owner_id=9,
        owner_email="capa.owner@example.com",
        assigned_to_email="capa.owner@example.com",
        created_at="2026-08-18T12:00:00+00:00",
    )

    with (
        patch(
            "src.domain.services.reference_number.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-9999"),
        ),
        patch(
            "src.api.routes.actions.get_audit_finding_capa_for_tenant",
            new=AsyncMock(return_value=existing),
        ) as lookup,
        patch(
            "src.api.routes.actions._capa_to_response",
            new=AsyncMock(return_value=existing_response),
        ),
        patch(
            "src.api.routes.actions._resolve_owner_email",
            new=AsyncMock(return_value="capa.owner@example.com"),
        ),
        patch("src.api.routes.actions.record_audit_event", new=AsyncMock()) as audit_mock,
    ):
        response = await create_action(
            ActionCreate(
                title="CAPA: duplicate",
                description="Operator shortcut",
                source_type="audit_finding",
                source_id=203,
                priority="high",
            ),
            db=db,
            current_user=current_user,
        )

    lookup.assert_awaited_once()
    db.rollback.assert_awaited_once()
    audit_mock.assert_not_awaited()
    assert response.id == 74
    assert response.reference_number == "CAPA-2026-0010"
    assert response.assigned_to_email == "capa.owner@example.com"
    assert response.source_id == 203
