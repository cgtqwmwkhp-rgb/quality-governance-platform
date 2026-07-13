"""Integration tests for audit event recording.

CUJ-IMMU-01: domain mutations bridge into AuditLogEntry via record_audit_event.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.domain.models.incident import IncidentSeverity, IncidentStatus, IncidentType
from src.infrastructure.middleware.tenant_context import apply_tenant_guc
from tests.factories import IncidentFactory


@pytest.fixture
async def test_incident(test_session, test_user):
    """Create a test incident."""
    incident = IncidentFactory.build(
        title="Test Incident for Audit",
        description="Description",
        incident_type=IncidentType.QUALITY,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        reference_number=f"INC-AUDIT-{uuid.uuid4().hex[:8]}",
        reporter_id=test_user.id,
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)
    return incident


async def test_incident_creation_records_audit_event(client: AsyncClient, auth_headers, test_session, test_tenant):
    """Creating an incident persists an immutable AuditLogEntry for Admin Audit Trail."""
    data = {
        "title": "Audit Test Incident",
        "description": "Testing audit log",
        "incident_type": IncidentType.QUALITY,
        "severity": IncidentSeverity.MEDIUM,
        "status": IncidentStatus.REPORTED,
        "incident_date": "2026-01-04T12:00:00Z",
        "location": "Test Lab",
    }
    response = await client.post("/api/v1/incidents/", json=data, headers=auth_headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["id"] is not None
    assert res_data["title"] == "Audit Test Incident"

    # FORCE RLS on audit_log_entries — bind tenant GUC for the test session read
    await apply_tenant_guc(test_session, test_tenant.id)
    result = await test_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.tenant_id == test_tenant.id,
            AuditLogEntry.entity_type == "incident",
            AuditLogEntry.entity_id == str(res_data["id"]),
        )
    )
    assert result.scalar_one_or_none() is not None
