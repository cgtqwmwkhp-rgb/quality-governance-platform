"""CUJ-IMMU-01: record_audit_event → AuditLogEntry bridge contracts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.audit_service import record_audit_event


@pytest.mark.asyncio
async def test_record_audit_event_persists_via_audit_log_service():
    """With tenant_id, bridge flushes an immutable AuditLogEntry (commit=False)."""
    db = AsyncMock()
    entry = MagicMock(id=42)

    with patch("src.domain.services.audit_service.AuditLogService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.log = AsyncMock(return_value=entry)
        mock_cls.return_value = mock_svc

        event = await record_audit_event(
            db=db,
            event_type="capa.created",
            entity_type="capa",
            entity_id="7",
            action="create",
            description="CAPA CAPA-1 created",
            payload={"title": "Fix"},
            user_id=5,
            tenant_id=10,
            request_id="req-1",
        )

    mock_cls.assert_called_once_with(db)
    mock_svc.log.assert_awaited_once()
    kwargs = mock_svc.log.await_args.kwargs
    assert kwargs["tenant_id"] == 10
    assert kwargs["entity_type"] == "capa"
    assert kwargs["entity_id"] == "7"
    assert kwargs["action"] == "create"
    assert kwargs["user_id"] == 5
    assert kwargs["new_values"] == {"title": "Fix"}
    assert kwargs["old_values"] is None
    assert kwargs["commit"] is False
    assert kwargs["metadata"]["event_type"] == "capa.created"
    assert event.id == 42


@pytest.mark.asyncio
async def test_record_audit_event_delete_maps_payload_to_old_values():
    db = AsyncMock()
    entry = MagicMock(id=99)

    with patch("src.domain.services.audit_service.AuditLogService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.log = AsyncMock(return_value=entry)
        mock_cls.return_value = mock_svc

        await record_audit_event(
            db=db,
            event_type="incident.deleted",
            entity_type="incident",
            entity_id="3",
            action="delete",
            payload={"incident_id": 3},
            user_id=1,
            tenant_id=2,
        )

    kwargs = mock_svc.log.await_args.kwargs
    assert kwargs["old_values"] == {"incident_id": 3}
    assert kwargs["new_values"] is None


@pytest.mark.asyncio
async def test_record_audit_event_skips_persist_without_tenant():
    """Honest degradation: no tenant → observability only, no AuditLogService call."""
    db = AsyncMock()

    with patch("src.domain.services.audit_service.AuditLogService") as mock_cls:
        event = await record_audit_event(
            db=db,
            event_type="complaint.created",
            entity_type="complaint",
            entity_id="1",
            action="create",
            payload={"title": "x"},
            user_id=1,
            tenant_id=None,
        )

    mock_cls.assert_not_called()
    assert event.id is None
    assert event.event_type == "complaint.created"


@pytest.mark.asyncio
async def test_record_audit_event_requires_explicit_tenant_id():
    """Domain bridge does not import infrastructure tenant_context (D09)."""
    db = AsyncMock()

    with patch("src.domain.services.audit_service.AuditLogService") as mock_cls:
        event = await record_audit_event(
            db=db,
            event_type="incident.updated",
            entity_type="incident",
            entity_id="9",
            action="update",
            payload={"title": "y"},
            user_id=3,
            # tenant_id omitted on purpose
        )

    mock_cls.assert_not_called()
    assert event.id is None
