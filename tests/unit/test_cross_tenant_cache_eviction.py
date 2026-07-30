"""B-6: cross-tenant edits must evict (and audit) the record's tenant, not the caller's.

Mirrors the near-miss/RTA fix in #1382. A superuser in tenant 1 editing a row that
lives in tenant 7 must invalidate tenant 7's register cache and file the audit
event under tenant 7 — otherwise the owning tenant keeps a stale list and never
sees the audit entry.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.routes.near_miss import delete_near_miss as delete_near_miss_route
from src.api.routes.rtas import delete_rta as delete_rta_route
from src.api.schemas.complaint import ComplaintUpdate
from src.api.schemas.incident import IncidentUpdate
from src.domain.services.complaint_service import ComplaintService
from src.domain.services.incident_service import IncidentService
from src.domain.services.near_miss_service import NearMissService
from src.domain.services.rta_service import RTAService


def _incident(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 7,
        "reference_number": "INC-2026-0001",
        "title": "Lift near-miss",
        "status": "reported",
        "lessons_learnt": None,
        "closed_at": None,
        "closed_by_id": None,
        "updated_at": None,
        "updated_by_id": None,
        "medical_assistance": None,
        "first_aid_given": False,
        "emergency_services": None,
        "emergency_services_called": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _complaint(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 7,
        "reference_number": "CMP-2026-0001",
        "title": "Service delay",
        "status": "open",
        "lessons_learnt": None,
        "closed_at": None,
        "closed_by_id": None,
        "updated_at": None,
        "updated_by_id": None,
        "received_date": None,
        "response_sla_hours": None,
        "response_due_at": None,
        "first_response_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _near_miss(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 7,
        "reference_number": "NM-2026-0001",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _rta(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 7,
        "reference_number": "RTA-2026-0001",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _db():
    return SimpleNamespace(
        execute=AsyncMock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_incident_update_evicts_and_audits_the_records_tenant():
    incident = _incident(tenant_id=7)
    svc = IncidentService(_db())
    svc.get_incident = AsyncMock(return_value=incident)

    with (
        patch("src.domain.services.incident_service.record_audit_event", AsyncMock()) as audit,
        patch("src.domain.services.incident_service.invalidate_tenant_cache", AsyncMock()) as evict,
    ):
        await svc.update_incident(
            1,
            IncidentUpdate(title="Updated by platform admin"),
            user_id=42,
            tenant_id=1,
            skip_tenant_check=True,
            request_id="req-b6-inc-upd",
        )

    assert evict.await_args.args[0] == 7
    assert audit.await_args.kwargs["tenant_id"] == 7


@pytest.mark.asyncio
async def test_incident_delete_evicts_and_audits_the_records_tenant():
    incident = _incident(tenant_id=7)
    svc = IncidentService(_db())
    svc.get_incident = AsyncMock(return_value=incident)

    with (
        patch("src.domain.services.incident_service.record_audit_event", AsyncMock()) as audit,
        patch("src.domain.services.incident_service.invalidate_tenant_cache", AsyncMock()) as evict,
    ):
        await svc.delete_incident(
            1,
            user_id=42,
            tenant_id=1,
            skip_tenant_check=True,
            request_id="req-b6-inc-del",
        )

    assert evict.await_args.args[0] == 7
    assert audit.await_args.kwargs["tenant_id"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_tenant_id", [1, None])
async def test_near_miss_delete_evicts_and_audits_the_records_tenant(caller_tenant_id):
    near_miss = _near_miss(tenant_id=7)
    db = _db()
    svc = NearMissService(db)
    svc.get_near_miss = AsyncMock(return_value=near_miss)

    with (
        patch("src.domain.services.near_miss_service.record_audit_event", AsyncMock()) as audit,
        patch("src.domain.services.near_miss_service.invalidate_tenant_cache", AsyncMock()) as evict,
    ):
        await svc.delete_near_miss(
            1,
            user_id=42,
            tenant_id=caller_tenant_id,
            skip_tenant_check=True,
            request_id="req-b6-nm-del",
        )

    db.delete.assert_awaited_once_with(near_miss)
    db.commit.assert_awaited_once()
    evict.assert_awaited_once_with(7, "near_miss")
    assert audit.await_args.kwargs["tenant_id"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_tenant_id", [1, None])
async def test_rta_delete_evicts_and_audits_the_records_tenant(caller_tenant_id):
    rta = _rta(tenant_id=7)
    db = _db()
    svc = RTAService(db)
    svc.get_rta = AsyncMock(return_value=rta)

    with (
        patch("src.domain.services.rta_service.record_audit_event", AsyncMock()) as audit,
        patch("src.domain.services.rta_service.invalidate_tenant_cache", AsyncMock()) as evict,
    ):
        await svc.delete_rta(
            1,
            user_id=42,
            tenant_id=caller_tenant_id,
            skip_tenant_check=True,
            request_id="req-b6-rta-del",
        )

    db.delete.assert_awaited_once_with(rta)
    db.commit.assert_awaited_once()
    evict.assert_awaited_once_with(7, "rtas")
    assert audit.await_args.kwargs["tenant_id"] == 7


@pytest.mark.asyncio
async def test_near_miss_delete_route_delegates_to_tenant_aware_service():
    db = _db()
    user = SimpleNamespace(id=42, tenant_id=1, is_superuser=True)

    with patch("src.api.routes.near_miss.NearMissService") as service_class:
        delete = AsyncMock()
        service_class.return_value.delete_near_miss = delete

        await delete_near_miss_route(7, db, user, "req-route-nm-del")

    service_class.assert_called_once_with(db)
    delete.assert_awaited_once_with(
        7,
        user_id=42,
        tenant_id=1,
        request_id="req-route-nm-del",
        skip_tenant_check=True,
    )


@pytest.mark.asyncio
async def test_rta_delete_route_delegates_to_tenant_aware_service():
    db = _db()
    user = SimpleNamespace(id=42, tenant_id=1, is_superuser=True)

    with patch("src.api.routes.rtas.RTAService") as service_class:
        delete = AsyncMock()
        service_class.return_value.delete_rta = delete

        await delete_rta_route(7, db, user, "req-route-rta-del")

    service_class.assert_called_once_with(db)
    delete.assert_awaited_once_with(
        7,
        user_id=42,
        tenant_id=1,
        request_id="req-route-rta-del",
        skip_tenant_check=True,
    )


@pytest.mark.asyncio
async def test_complaint_update_evicts_and_audits_the_records_tenant():
    complaint = _complaint(tenant_id=7)
    svc = ComplaintService(_db())
    svc.get_complaint = AsyncMock(return_value=complaint)

    with (
        patch("src.domain.services.complaint_service.record_audit_event", AsyncMock()) as audit,
        patch("src.domain.services.complaint_service.invalidate_tenant_cache", AsyncMock()) as evict,
    ):
        await svc.update_complaint(
            1,
            ComplaintUpdate(title="Updated by platform admin"),
            user_id=42,
            tenant_id=1,
            skip_tenant_check=True,
            request_id="req-b6-cmp-upd",
        )

    assert evict.await_args.args[0] == 7
    assert audit.await_args.kwargs["tenant_id"] == 7
