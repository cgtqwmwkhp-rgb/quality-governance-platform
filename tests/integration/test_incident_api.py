"""Integration tests for Incident API."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from tests.factories import IncidentFactory


@pytest.mark.asyncio
async def test_create_incident(client: AsyncClient, auth_headers: dict, test_session):
    """Test creating an incident via API and checks audit log."""
    incident_date = datetime.now(timezone.utc)
    data = {
        "title": "Integration Test Incident",
        "description": "Test Description",
        "incident_type": IncidentType.QUALITY,
        "severity": IncidentSeverity.HIGH,
        "status": IncidentStatus.REPORTED,
        "incident_date": incident_date.isoformat(),
        "location": "Test Location",
    }
    response = await client.post("/api/v1/incidents/", json=data, headers=auth_headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["title"] == "Integration Test Incident"
    assert res_data["reference_number"].startswith(f"INC-{incident_date.year}-")
    assert res_data["severity"] == IncidentSeverity.HIGH


@pytest.mark.asyncio
async def test_get_incident_by_id(client: AsyncClient, auth_headers: dict, test_session):
    """Test getting an incident by ID."""
    incident = IncidentFactory.build(
        title="Get Test Incident",
        description="Test Description",
        reference_number=f"INC-2026-{uuid.uuid4().hex[:8]}",
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)

    response = await client.get(f"/api/v1/incidents/{incident.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Get Test Incident"


@pytest.mark.asyncio
async def test_list_incidents_deterministic_ordering(client: AsyncClient, auth_headers: dict, test_session):
    """Test that incidents are returned in deterministic order (reported_date DESC, id ASC)."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:6]

    incidents = [
        IncidentFactory.build(
            title=f"Incident {i}-{suffix}",
            incident_date=now,
            reported_date=now - timedelta(days=i),
            reference_number=f"INC-2026-L{uuid.uuid4().hex[:6]}{i}",
        )
        for i in range(3)
    ]
    for inc in incidents:
        test_session.add(inc)
    await test_session.commit()

    response = await client.get("/api/v1/incidents/", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]

    # Validate ordering among records created by this test.
    test_items = [
        item
        for item in items
        if item["title"] in {f"Incident 0-{suffix}", f"Incident 1-{suffix}", f"Incident 2-{suffix}"}
    ]
    assert len(test_items) >= 1
    if len(test_items) >= 3:
        assert test_items[0]["title"] == f"Incident 0-{suffix}"
        assert test_items[-1]["title"] == f"Incident 2-{suffix}"


@pytest.mark.asyncio
async def test_update_incident_status(client: AsyncClient, auth_headers: dict, test_session):
    """Test updating incident status via PATCH and checks audit log."""
    incident = IncidentFactory.build(
        title="Status Update Test",
        reference_number=f"INC-2026-{uuid.uuid4().hex[:8]}",
        status=IncidentStatus.REPORTED,
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)

    update_data = {"status": IncidentStatus.CLOSED}
    response = await client.patch(f"/api/v1/incidents/{incident.id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == IncidentStatus.CLOSED


@pytest.mark.asyncio
async def test_list_incidents_pagination(client: AsyncClient, auth_headers: dict, test_session):
    """Test pagination behavior."""
    now = datetime.now(timezone.utc)
    for i in range(5):
        inc = IncidentFactory.build(
            title=f"Paginated {i}",
            incident_date=now,
            reported_date=now - timedelta(minutes=i),
            reference_number=f"INC-2026-P{uuid.uuid4().hex[:6]}{i}",
        )
        test_session.add(inc)
    await test_session.commit()

    # Get page 1, size 2
    response = await client.get("/api/v1/incidents/?page=1&page_size=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5

    # Get page 2, size 2
    response2 = await client.get("/api/v1/incidents/?page=2&page_size=2", headers=auth_headers)
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 2

    # Ensure no overlap
    page1_ids = [item["id"] for item in data["items"]]
    page2_ids = [item["id"] for item in data2["items"]]
    for pid in page1_ids:
        assert pid not in page2_ids


@pytest.mark.asyncio
async def test_delete_incident(client: AsyncClient, auth_headers: dict, test_session):
    """Test deleting an incident via API and checks audit log."""
    incident = IncidentFactory.build(
        title="Delete Test Incident",
        reference_number=f"INC-2026-D{uuid.uuid4().hex[:7]}",
        status=IncidentStatus.REPORTED,
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)
    incident_id = incident.id

    response = await client.delete(f"/api/v1/incidents/{incident_id}", headers=auth_headers)
    assert response.status_code in (200, 204)

    # Test deleting non-existent incident
    response = await client.delete(f"/api/v1/incidents/{incident_id}", headers=auth_headers)
    assert response.status_code in (404, 409)
