"""Unit tests: PATCH /investigations/{id} writes revision events (PX-141).

The generic PATCH handler is the primary editor for investigation status and
narrative fields, but it emitted no revision event. STATUS_CHANGED was therefore
never written by any route in the codebase, so the timeline's "Status changes"
and "Field updates" filters were permanently empty.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.investigations import update_investigation
from src.api.schemas.investigation import InvestigationRunUpdate
from src.domain.models.investigation import InvestigationStatus
from src.domain.services.investigation_service import InvestigationService


def _investigation(**overrides):
    base = dict(
        id=42,
        tenant_id=7,
        template_id=1,
        version=3,
        status=InvestigationStatus.IN_PROGRESS,
        title="Fork lift near miss",
        description="Original description",
        data={"summary": "before"},
        reference_number="INV-42",
        started_at=datetime(2026, 7, 1),
        completed_at=None,
        closed_at=None,
        assigned_entity_type="incident",
        assigned_entity_id=99,
        assigned_entity_reference=None,
        created_at=datetime(2026, 7, 1),
        updated_at=datetime(2026, 7, 1),
        updated_by_id=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _db(investigation):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=investigation)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _request():
    return MagicMock(headers={"X-Request-ID": "req-123"})


async def _patch(investigation, payload):
    db = _db(investigation)
    with (
        patch(
            "src.api.routes.investigations._ensure_investigation_ready_for_status",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.domain.services.investigation_service.resolve_assigned_entity_reference",
            new=AsyncMock(return_value="INC-99"),
        ),
        patch.object(InvestigationService, "create_revision_event", new=AsyncMock()) as spy,
    ):
        await update_investigation(
            request=_request(),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(**payload),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7),
        )
    return spy


@pytest.mark.asyncio
async def test_status_change_emits_status_changed_event():
    spy = await _patch(_investigation(), {"status": "completed"})

    assert spy.await_count == 1
    kwargs = spy.await_args.kwargs
    assert kwargs["event_type"] == "STATUS_CHANGED"
    assert kwargs["field_path"] == "status"
    assert kwargs["old_value"] == "in_progress"
    assert kwargs["new_value"] == "completed"
    assert kwargs["actor_id"] == 11


@pytest.mark.asyncio
async def test_scalar_field_edit_emits_data_updated_event_with_values():
    spy = await _patch(_investigation(), {"title": "Fork lift collision"})

    assert spy.await_count == 1
    kwargs = spy.await_args.kwargs
    assert kwargs["event_type"] == "DATA_UPDATED"
    assert kwargs["field_path"] == "title"
    assert kwargs["old_value"] == "Fork lift near miss"
    assert kwargs["new_value"] == "Fork lift collision"


@pytest.mark.asyncio
async def test_json_blob_edit_records_field_path_without_inlining_the_blob():
    spy = await _patch(_investigation(), {"data": {"summary": "after"}})

    assert spy.await_count == 1
    kwargs = spy.await_args.kwargs
    assert kwargs["event_type"] == "DATA_UPDATED"
    assert kwargs["field_path"] == "data"
    assert kwargs["old_value"] is None
    assert kwargs["new_value"] is None


@pytest.mark.asyncio
async def test_unchanged_field_emits_no_event():
    spy = await _patch(_investigation(), {"status": "in_progress", "title": "Fork lift near miss"})

    assert spy.await_count == 0


@pytest.mark.asyncio
async def test_multiple_changed_fields_emit_one_event_each():
    spy = await _patch(_investigation(), {"status": "completed", "description": "Revised description"})

    assert spy.await_count == 2
    emitted = {call.kwargs["field_path"]: call.kwargs["event_type"] for call in spy.await_args_list}
    assert emitted == {"status": "STATUS_CHANGED", "description": "DATA_UPDATED"}


@pytest.mark.asyncio
async def test_revision_events_carry_request_id_for_correlation():
    spy = await _patch(_investigation(), {"status": "completed"})

    assert spy.await_args.kwargs["metadata"] == {
        "request_id": "req-123",
        "source": "investigation_patch",
    }
