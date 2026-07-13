"""Integration contracts: domain mutations persist immutable AuditLogEntry rows.

CUJ-IMMU-01 — Admin Audit Trail must reflect CAPA / incident / complaint writes.
"""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.domain.services.audit_log_service import AuditLogService
from src.domain.services.audit_service import record_audit_event
from src.infrastructure.middleware.tenant_context import apply_tenant_guc


@pytest.mark.asyncio
async def test_record_audit_event_persists_hash_chained_entry(test_session, test_tenant, test_user):
    """Direct bridge: flush creates a queryable AuditLogEntry with genesis chain."""
    event = await record_audit_event(
        db=test_session,
        event_type="capa.created",
        entity_type="capa",
        entity_id="1001",
        action="create",
        description="CAPA CAPA-TEST-1 created",
        payload={"title": "Bridge proof"},
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        request_id="immu-01-direct",
    )
    await test_session.commit()

    assert event.id is not None

    result = await test_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.tenant_id == test_tenant.id,
            AuditLogEntry.entity_type == "capa",
            AuditLogEntry.entity_id == "1001",
        )
    )
    entry = result.scalar_one()
    assert entry.id == event.id
    assert entry.action == "create"
    assert entry.sequence == 1
    assert entry.previous_hash == AuditLogService.GENESIS_HASH
    assert entry.entry_hash
    assert entry.user_id == test_user.id
    assert entry.new_values == {"title": "Bridge proof"}
    assert entry.entry_metadata["event_type"] == "capa.created"


@pytest.mark.asyncio
async def test_incident_create_persists_audit_log_entry(client: AsyncClient, auth_headers, test_session, test_tenant):
    """API create incident must leave an immutable audit row for Admin Audit Trail."""
    data = {
        "title": "IMMU-01 Incident",
        "description": "Domain mutation audit bridge",
        "incident_type": "injury",
        "severity": "low",
        "status": "reported",
        "incident_date": datetime.now(timezone.utc).isoformat(),
        "location": "Lab",
        "department": "QA",
    }
    response = await client.post("/api/v1/incidents/", json=data, headers=auth_headers)
    assert response.status_code == 201
    incident_id = str(response.json()["id"])

    # FORCE RLS on audit_log_entries — bind tenant GUC for the test session read
    await apply_tenant_guc(test_session, test_tenant.id)
    result = await test_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.tenant_id == test_tenant.id,
            AuditLogEntry.entity_type == "incident",
            AuditLogEntry.entity_id == incident_id,
            AuditLogEntry.action == "create",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.entry_hash
    assert entry.entry_metadata.get("event_type") == "incident.created"


@pytest.mark.asyncio
async def test_complaint_create_persists_audit_log_entry(client: AsyncClient, auth_headers, test_session, test_tenant):
    data = {
        "title": "IMMU-01 Complaint",
        "description": "Domain mutation audit bridge",
        "complaint_type": "service",
        "priority": "medium",
        "received_date": datetime.now(timezone.utc).isoformat(),
        "complainant_name": "Auditor",
        "complainant_email": "auditor@example.com",
    }
    response = await client.post("/api/v1/complaints/", json=data, headers=auth_headers)
    assert response.status_code == 201
    complaint_id = str(response.json()["id"])

    await apply_tenant_guc(test_session, test_tenant.id)
    result = await test_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.tenant_id == test_tenant.id,
            AuditLogEntry.entity_type == "complaint",
            AuditLogEntry.entity_id == complaint_id,
            AuditLogEntry.action == "create",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.entry_metadata.get("event_type") == "complaint.created"
