"""Integration tests for Incident API."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType


@pytest.mark.asyncio
async def test_create_incident(client: AsyncClient, auth_headers: dict):
    """Test creating an incident via API."""
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
    response = await client.post("/api/v1/incidents", json=data, headers=auth_headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["title"] == "Integration Test Incident"
    assert res_data["reference_number"].startswith(f"INC-{incident_date.year}-")
    assert res_data["severity"] == IncidentSeverity.HIGH


@pytest.mark.asyncio
async def test_get_incident_by_id(client: AsyncClient, auth_headers: dict, test_session):
    """Test getting an incident by ID."""
    # Create incident directly in DB
    incident = Incident(
        title="Get Test Incident",
        description="Test Description",
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        reference_number="INC-2026-9999",
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
    
    # Create 3 incidents with different reported dates
    incidents = [
        Incident(
            title=f"Incident {i}",
            description="Test",
            incident_date=now,
            reported_date=now - timedelta(days=i),
            reference_number=f"INC-2026-000{i}",
        )
        for i in range(3)
    ]
    for inc in incidents:
        test_session.add(inc)
    await test_session.commit()

    response = await client.get("/api/v1/incidents", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    
    # Should be ordered by reported_date DESC (newest first)
    # Incident 0 is newest, Incident 2 is oldest
    assert items[0]["title"] == "Incident 0"
    assert items[1]["title"] == "Incident 1"
    assert items[2]["title"] == "Incident 2"


@pytest.mark.asyncio
async def test_update_incident_status(client: AsyncClient, auth_headers: dict, test_session):
    """Test updating incident status via PATCH."""
    incident = Incident(
        title="Status Update Test",
        description="Test",
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        reference_number="INC-2026-8888",
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
    # Create 5 incidents
    for i in range(5):
        inc = Incident(
            title=f"Paginated {i}",
            description="Test",
            incident_date=now,
            reported_date=now - timedelta(minutes=i),
            reference_number=f"INC-2026-P00{i}",
        )
        test_session.add(inc)
    await test_session.commit()

    # Get page 1, size 2
    response = await client.get("/api/v1/incidents?page=1&page_size=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5
    
    # Get page 2, size 2
    response2 = await client.get("/api/v1/incidents?page=2&page_size=2", headers=auth_headers)
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 2
    
    # Ensure no overlap
    page1_ids = [item["id"] for item in data["items"]]
    page2_ids = [item["id"] for item in data2["items"]]
    for pid in page1_ids:
        assert pid not in page2_ids
