"""Integration tests for audit event recording."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditEvent
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType


@pytest.fixture
async def test_incident(test_session, test_user):
    """Create a test incident."""
    from datetime import datetime, timezone

    incident = Incident(
        title="Test Incident for Audit",
        description="Description",
        incident_type=IncidentType.QUALITY,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        reference_number="INC-2026-AUDIT",
        reporter_id=test_user.id,
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)
    return incident


async def test_incident_creation_records_audit_event(client: AsyncClient, auth_headers, test_session):
    """Test that creating an incident records an audit event."""
    data = {
        "title": "Audit Test Incident",
        "description": "Testing audit log",
        "incident_type": IncidentType.QUALITY,
        "severity": IncidentSeverity.MEDIUM,
        "status": IncidentStatus.REPORTED,
        "incident_date": "2026-01-04T12:00:00Z",
        "location": "Test Lab",
    }
    response = await client.post("/api/v1/incidents", json=data, headers=auth_headers)
    assert response.status_code == 201
    incident_id = response.json()["id"]

    # Verify audit event exists
    result = await test_session.execute(
        select(AuditEvent).where(
            AuditEvent.resource_type == "incident",
            AuditEvent.resource_id == str(incident_id),
            AuditEvent.event_type == "incident.created",
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.action == "create"
    assert "created" in event.description

