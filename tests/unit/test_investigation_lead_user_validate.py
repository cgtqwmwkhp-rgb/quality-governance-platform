"""Unit tests: investigation lead/reviewer ids must resolve in-tenant (PX-168b).

PATCH /investigations/{id} previously setattr ``assigned_to_user_id`` with no
existence or tenancy check — the same hole actions closed for ``owner_id``.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.investigations import update_investigation
from src.api.schemas.investigation import InvestigationRunUpdate
from src.domain.exceptions import BadRequestError
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
        assigned_to_user_id=None,
        reviewer_user_id=None,
        assigned_entity_type="incident",
        assigned_entity_id=99,
        assigned_entity_reference=None,
        created_at=datetime(2026, 7, 1),
        updated_at=datetime(2026, 7, 1),
        updated_by_id=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _db(investigation, *, lookup_user=None):
    db = AsyncMock()

    inv_result = MagicMock()
    inv_result.scalar_one_or_none = MagicMock(return_value=investigation)

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=lookup_user)

    async def _execute(stmt):  # noqa: ARG001 — statement inspected only by ORM in prod
        # First execute loads the investigation; subsequent ones resolve User refs.
        if not getattr(_execute, "_loaded_inv", False):
            _execute._loaded_inv = True
            return inv_result
        return user_result

    _execute._loaded_inv = False
    db.execute = AsyncMock(side_effect=_execute)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _request():
    return MagicMock(headers={"X-Request-ID": "req-lead"})


@pytest.mark.asyncio
async def test_patch_lead_rejects_unknown_user_id():
    inv = _investigation()
    db = _db(inv, lookup_user=None)

    with pytest.raises(BadRequestError) as exc_info:
        await update_investigation(
            request=_request(),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(assigned_to_user_id=99999),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7, is_superuser=False),
        )

    assert exc_info.value.code == "INVESTIGATION_USER_NOT_FOUND"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_lead_rejects_cross_tenant_user():
    inv = _investigation()
    other_tenant_user = SimpleNamespace(id=55, tenant_id=99, is_active=True)
    db = _db(inv, lookup_user=other_tenant_user)

    with pytest.raises(BadRequestError) as exc_info:
        await update_investigation(
            request=_request(),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(assigned_to_user_id=55),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7, is_superuser=False),
        )

    assert exc_info.value.code == "INVESTIGATION_USER_WRONG_TENANT"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_lead_rejects_inactive_user():
    inv = _investigation()
    inactive = SimpleNamespace(id=55, tenant_id=7, is_active=False)
    db = _db(inv, lookup_user=inactive)

    with pytest.raises(BadRequestError) as exc_info:
        await update_investigation(
            request=_request(),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(assigned_to_user_id=55),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7, is_superuser=False),
        )

    assert exc_info.value.code == "INVESTIGATION_USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_lead_accepts_active_tenant_user_and_emits_revision():
    inv = _investigation()
    lead = SimpleNamespace(id=55, tenant_id=7, is_active=True)
    db = _db(inv, lookup_user=lead)

    with (
        patch(
            "src.domain.services.investigation_service.resolve_assigned_entity_reference",
            new=AsyncMock(return_value="INC-99"),
        ),
        patch.object(InvestigationService, "create_revision_event", new=AsyncMock()) as spy,
    ):
        await update_investigation(
            request=_request(),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(assigned_to_user_id=55),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7, is_superuser=False),
        )

    assert inv.assigned_to_user_id == 55
    assert spy.await_count == 1
    assert spy.await_args.kwargs["field_path"] == "assigned_to_user_id"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_patch_clearing_lead_skips_user_lookup():
    inv = _investigation(assigned_to_user_id=55)
    db = _db(inv, lookup_user=None)

    with (
        patch(
            "src.domain.services.investigation_service.resolve_assigned_entity_reference",
            new=AsyncMock(return_value="INC-99"),
        ),
        patch.object(InvestigationService, "create_revision_event", new=AsyncMock()),
    ):
        await update_investigation(
            request=_request(),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(assigned_to_user_id=None),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7, is_superuser=False),
        )

    # Clearing must not attempt a User lookup (execute only loads the investigation).
    assert db.execute.await_count == 1
    assert inv.assigned_to_user_id is None
