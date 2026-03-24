from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.complaints import delete_complaint_running_sheet_entry
from src.api.routes.incidents import add_incident_running_sheet_entry
from src.api.routes.near_miss import add_near_miss_running_sheet_entry, delete_near_miss_running_sheet_entry
from src.api.routes.rtas import delete_running_sheet_entry
from src.api.schemas.running_sheet import RunningSheetEntryCreate


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.asyncio
async def test_add_incident_running_sheet_entry_records_audit_and_tenant() -> None:
    incident = SimpleNamespace(id=7, tenant_id=22, reference_number="INC-7")
    service = SimpleNamespace(get_incident=AsyncMock(return_value=incident))

    async def refresh(entry):
        entry.id = 101
        entry.created_at = "2026-03-24T00:00:00Z"

    db = SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    current_user = SimpleNamespace(id=5, email="owner@example.com", tenant_id=22, is_superuser=False)

    with (
        patch("src.api.routes.incidents.IncidentService", return_value=service),
        patch("src.api.routes.incidents.record_audit_event", AsyncMock()) as audit_mock,
    ):
        entry = await add_incident_running_sheet_entry(
            incident_id=7,
            payload=RunningSheetEntryCreate(content="Initial note"),
            db=db,
            current_user=current_user,
            request_id="req-1",
        )

    assert entry.tenant_id == 22
    assert entry.author_id == 5
    assert entry.author_email == "owner@example.com"
    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["event_type"] == "incident.runner_sheet_entry.created"


@pytest.mark.asyncio
async def test_delete_complaint_running_sheet_entry_blocks_unauthorized_delete() -> None:
    complaint = SimpleNamespace(id=8, tenant_id=44, reference_number="COMP-8")
    service = SimpleNamespace(get_complaint=AsyncMock(return_value=complaint))
    entry = SimpleNamespace(id=13, complaint_id=8, author_id=99, entry_type="note")
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(entry)))
    current_user = SimpleNamespace(
        id=5,
        email="owner@example.com",
        tenant_id=44,
        is_superuser=False,
        has_permission=lambda permission: False,
    )

    with patch("src.api.routes.complaints.ComplaintService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await delete_complaint_running_sheet_entry(
                complaint_id=8,
                entry_id=13,
                db=db,
                current_user=current_user,
                request_id="req-2",
            )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_add_near_miss_running_sheet_entry_records_audit_and_tenant() -> None:
    near_miss = SimpleNamespace(id=4, tenant_id=9, reference_number="NM-4")
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(near_miss)),
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    current_user = SimpleNamespace(id=2, email="safety@example.com", tenant_id=9, is_superuser=False)

    with patch("src.api.routes.near_miss.record_audit_event", AsyncMock()) as audit_mock:
        entry = await add_near_miss_running_sheet_entry(
            near_miss_id=4,
            payload=RunningSheetEntryCreate(content="Escalated to team leader"),
            db=db,
            current_user=current_user,
            request_id="req-3",
        )

    assert entry.tenant_id == 9
    assert entry.author_email == "safety@example.com"
    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["event_type"] == "near_miss.runner_sheet_entry.created"


@pytest.mark.asyncio
async def test_delete_near_miss_running_sheet_entry_allows_update_permission() -> None:
    near_miss = SimpleNamespace(id=4, tenant_id=9, reference_number="NM-4")
    entry = SimpleNamespace(id=12, near_miss_id=4, tenant_id=9, author_id=77, entry_type="note")
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(near_miss), _FakeResult(entry)]),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    current_user = SimpleNamespace(
        id=2,
        email="safety@example.com",
        tenant_id=9,
        is_superuser=False,
        has_permission=lambda permission: permission == "near_miss:update",
    )

    with patch("src.api.routes.near_miss.record_audit_event", AsyncMock()) as audit_mock:
        await delete_near_miss_running_sheet_entry(
            near_miss_id=4,
            entry_id=12,
            db=db,
            current_user=current_user,
            request_id="req-3b",
        )

    db.delete.assert_awaited_once_with(entry)
    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["event_type"] == "near_miss.runner_sheet_entry.deleted"


@pytest.mark.asyncio
async def test_delete_rta_running_sheet_entry_allows_author_and_audits() -> None:
    rta = SimpleNamespace(id=3, tenant_id=17, reference_number="RTA-3")
    entry = SimpleNamespace(id=6, rta_id=3, author_id=41, entry_type="note")
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(entry)),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    current_user = SimpleNamespace(
        id=41,
        email="driver@example.com",
        tenant_id=17,
        is_superuser=False,
        has_permission=lambda permission: False,
    )

    with (
        patch("src.api.routes.rtas._get_rta_or_404", AsyncMock(return_value=rta)),
        patch("src.api.routes.rtas.record_audit_event", AsyncMock()) as audit_mock,
    ):
        await delete_running_sheet_entry(
            rta_id=3,
            entry_id=6,
            db=db,
            current_user=current_user,
            request_id="req-4",
        )

    db.delete.assert_awaited_once_with(entry)
    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["event_type"] == "rta.runner_sheet_entry.deleted"
