"""Unit tests for investigation completion gate (Run021 GROUP 2 / PX-169)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.investigations import (
    ClosureReasonCode,
    _collect_readiness_reasons,
    _ensure_investigation_ready_for_status,
    update_investigation,
)
from src.api.schemas.investigation import InvestigationRunUpdate
from src.domain.exceptions import BadRequestError
from src.domain.models.investigation import AssignedEntityType, InvestigationStatus
from src.domain.services.investigation_service import InvestigationService


def _investigation(**overrides):
    now = datetime.now(timezone.utc)
    base = dict(
        id=7,
        tenant_id=1,
        template_id=1,
        level="medium",
        status=InvestigationStatus.IN_PROGRESS,
        started_at="2026-07-01T00:00:00",
        assigned_to_user_id=42,
        completed_at=None,
        closed_at=None,
        assigned_entity_type=AssignedEntityType.REPORTING_INCIDENT,
        assigned_entity_id=20,
        title="Warehouse slip investigation",
        reference_number="REF-2026-0007",
        created_at=now,
        updated_at=now,
        updated_by_id=1,
        data={
            "findings": "Slip on wet floor",
            "conclusion": "Improve housekeeping",
            "lead_investigator": "pat@example.com",
        },
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _empty_validation():
    result = MagicMock()
    result.reason_codes = []
    result.missing_items = []
    return result


@pytest.mark.asyncio
async def test_collect_readiness_reasons_flags_empty_summary_on_complete_gate():
    db = AsyncMock()
    inv = _investigation(
        status=InvestigationStatus.DRAFT,
        started_at=None,
        assigned_to_user_id=None,
        data={},
    )
    with (
        patch(
            "src.domain.services.investigation_closure_helpers.fetch_open_work_for_investigation",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            InvestigationService,
            "validate_closure",
            AsyncMock(return_value=_empty_validation()),
        ),
    ):
        reasons, _open_work, missing = await _collect_readiness_reasons(
            db,
            investigation=inv,
            investigation_id=7,
            current_user=SimpleNamespace(id=11, tenant_id=1),
            gate="complete",
        )

    assert ClosureReasonCode.INVESTIGATION_NOT_STARTED in reasons
    assert ClosureReasonCode.LEAD_INVESTIGATOR_NOT_ASSIGNED in reasons
    assert ClosureReasonCode.MISSING_FINDINGS in reasons
    assert ClosureReasonCode.MISSING_CONCLUSION in reasons
    assert ClosureReasonCode.STATUS_NOT_COMPLETE not in reasons
    assert any(item.field_key == "findings" for item in missing)


@pytest.mark.asyncio
async def test_collect_readiness_reasons_adds_status_not_complete_for_close_gate():
    db = AsyncMock()
    inv = _investigation(status=InvestigationStatus.IN_PROGRESS)
    with (
        patch(
            "src.domain.services.investigation_closure_helpers.fetch_open_work_for_investigation",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            InvestigationService,
            "validate_closure",
            AsyncMock(return_value=_empty_validation()),
        ),
    ):
        reasons, _, _ = await _collect_readiness_reasons(
            db,
            investigation=inv,
            investigation_id=7,
            current_user=SimpleNamespace(id=11, tenant_id=1),
            gate="close",
        )

    assert ClosureReasonCode.STATUS_NOT_COMPLETE in reasons


@pytest.mark.asyncio
async def test_patch_completed_rejects_when_summary_incomplete():
    inv = _investigation(status=InvestigationStatus.DRAFT, started_at=None, data={})
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=inv)
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(BadRequestError) as exc_info:
        await update_investigation(
            request=MagicMock(headers={"X-Request-ID": "req-1"}),
            investigation_id=7,
            investigation_data=InvestigationRunUpdate(status="completed"),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=1, is_superuser=False),
        )

    err = exc_info.value
    assert err.code == "CLOSURE_VALIDATION_FAILED"
    assert ClosureReasonCode.MISSING_FINDINGS in err.details["reasons"]


@pytest.mark.asyncio
async def test_patch_completed_allows_supervisor_override_for_open_work():
    inv = _investigation()
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=inv)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    open_item = MagicMock()
    open_item.kind = "investigation_action"
    open_item.id = 3
    open_item.reference_number = "INV-ACT-3"
    open_item.title = "Train staff"
    open_item.status = "open"
    open_item.action_key = "investigation_action:3"

    with (
        patch(
            "src.domain.services.investigation_closure_helpers.fetch_open_work_for_investigation",
            AsyncMock(return_value=[open_item]),
        ),
        patch.object(
            InvestigationService,
            "validate_closure",
            AsyncMock(return_value=_empty_validation()),
        ),
        patch.object(
            InvestigationService,
            "create_revision_event",
            new=AsyncMock(),
        ) as revision_spy,
        patch(
            "src.domain.services.investigation_service.resolve_assigned_entity_reference",
            AsyncMock(return_value="INC-2026-0020"),
        ),
        patch(
            "src.domain.services.lessons_learnt_promote.promote_lessons_to_case",
            AsyncMock(),
        ),
    ):
        await update_investigation(
            request=MagicMock(headers={"X-Request-ID": "req-2"}),
            investigation_id=7,
            investigation_data=InvestigationRunUpdate(
                status="completed",
                closure_override=True,
                closure_override_reason="Residual risk accepted by H&S manager",
            ),
            db=db,
            current_user=SimpleNamespace(
                id=11,
                tenant_id=1,
                is_superuser=True,
                reviewer_user_id=None,
            ),
        )

    assert revision_spy.await_count >= 1
    status_event = next(
        call for call in revision_spy.await_args_list if call.kwargs.get("event_type") == "STATUS_CHANGED"
    )
    assert status_event.kwargs["metadata"]["closure_override"] is True


@pytest.mark.asyncio
async def test_patch_completed_override_requires_reason():
    inv = _investigation()
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=inv)
    db.execute = AsyncMock(return_value=result)

    with (
        patch(
            "src.domain.services.investigation_closure_helpers.fetch_open_work_for_investigation",
            AsyncMock(return_value=[MagicMock()]),
        ),
        patch.object(
            InvestigationService,
            "validate_closure",
            AsyncMock(return_value=_empty_validation()),
        ),
    ):
        with pytest.raises(BadRequestError) as exc_info:
            await _ensure_investigation_ready_for_status(
                db,
                investigation=inv,
                investigation_id=7,
                current_user=SimpleNamespace(id=11, tenant_id=1, is_superuser=True),
                gate="complete",
                allow_open_work_override=True,
                override_reason="   ",
            )

    assert exc_info.value.code == "CLOSURE_OVERRIDE_REASON_REQUIRED"
