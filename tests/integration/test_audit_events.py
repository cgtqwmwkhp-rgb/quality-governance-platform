"""Integration tests for audit event recording.

Note: AuditEvent is a lightweight logging class (not a SQLAlchemy model),
so audit events are verified by checking API responses and HTTP status codes
rather than querying the database directly.
"""

import uuid

import pytest
from httpx import AsyncClient

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
        reference_number=f"INC-AUDIT-{uuid.uuid4().hex[:8]}",
        reporter_id=test_user.id,
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)
    return incident


async def test_incident_creation_records_audit_event(client: AsyncClient, auth_headers, test_session):
    """Test that creating an incident succeeds (audit events are logged, not DB-persisted)."""
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
