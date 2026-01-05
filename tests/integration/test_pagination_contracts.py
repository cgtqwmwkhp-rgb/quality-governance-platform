import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.domain.models.policy import Policy
from src.domain.models.incident import Incident, IncidentStatus, IncidentType, IncidentSeverity
from src.domain.models.complaint import Complaint, ComplaintStatus, ComplaintType, ComplaintPriority


@pytest.mark.asyncio
async def test_policies_list_pagination_and_ordering(client: AsyncClient, test_session: AsyncSession, auth_headers: dict):
    """Verify policies list endpoint has deterministic ordering and pagination."""
    # Create test data
    test_session.add_all([
        Policy(title="Policy 1", description="D1", reference_number="POL-2023-0001", created_by_id=1, updated_by_id=1),
        Policy(title="Policy 2", description="D2", reference_number="POL-2023-0002", created_by_id=1, updated_by_id=1),
        Policy(title="Policy 3", description="D3", reference_number="POL-2022-0001", created_by_id=1, updated_by_id=1),
    ])
    await test_session.commit()

    # Test default pagination
    response = await client.get("/api/v1/policies", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert [item["reference_number"] for item in data["items"]] == ["POL-2023-0002", "POL-2023-0001", "POL-2022-0001"]

    # Test custom pagination
    response = await client.get("/api/v1/policies?page=2&page_size=1", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 3
    assert data["page"] == 2
    assert data["page_size"] == 1
    assert data["items"][0]["reference_number"] == "POL-2023-0001"


@pytest.mark.asyncio
async def test_incidents_list_pagination_and_ordering(client: AsyncClient, test_session: AsyncSession, auth_headers: dict):
    """Verify incidents list endpoint has deterministic ordering and pagination."""
    # Create test data
    test_session.add_all([
        Incident(title="Incident 1", description="D1", incident_date=datetime(2023, 1, 1, tzinfo=timezone.utc), reported_date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc), reporter_id=1, created_by_id=1, updated_by_id=1, reference_number="INC-2023-0001", status=IncidentStatus.REPORTED, incident_type=IncidentType.OTHER, severity=IncidentSeverity.MEDIUM),
        Incident(title="Incident 2", description="D2", incident_date=datetime(2023, 1, 2, tzinfo=timezone.utc), reported_date=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc), reporter_id=1, created_by_id=1, updated_by_id=1, reference_number="INC-2023-0002", status=IncidentStatus.REPORTED, incident_type=IncidentType.OTHER, severity=IncidentSeverity.MEDIUM),
        Incident(title="Incident 3", description="D3", incident_date=datetime(2022, 1, 1, tzinfo=timezone.utc), reported_date=datetime(2022, 1, 1, 12, 0, 0, tzinfo=timezone.utc), reporter_id=1, created_by_id=1, updated_by_id=1, reference_number="INC-2022-0001", status=IncidentStatus.REPORTED, incident_type=IncidentType.OTHER, severity=IncidentSeverity.MEDIUM),
    ])
    await test_session.commit()

    # Test default pagination
    response = await client.get("/api/v1/incidents", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3
    assert [item["title"] for item in data["items"]] == ["Incident 2", "Incident 1", "Incident 3"]


@pytest.mark.asyncio
async def test_complaints_list_pagination_and_ordering(client: AsyncClient, test_session: AsyncSession, auth_headers: dict):
    """Verify complaints list endpoint has deterministic ordering and pagination."""
    # Create test data
    test_session.add_all([
        Complaint(title="C1", description="C1 desc", received_date=datetime(2023, 1, 1, tzinfo=timezone.utc), status=ComplaintStatus.RECEIVED, complainant_name="test", reference_number="COMP-2023-0001", complaint_type=ComplaintType.OTHER, priority=ComplaintPriority.MEDIUM, created_by_id=1, updated_by_id=1),
        Complaint(title="C2", description="C2 desc", received_date=datetime(2023, 1, 2, tzinfo=timezone.utc), status=ComplaintStatus.RECEIVED, complainant_name="test", reference_number="COMP-2023-0002", complaint_type=ComplaintType.OTHER, priority=ComplaintPriority.MEDIUM, created_by_id=1, updated_by_id=1),
        Complaint(title="C3", description="C3 desc", received_date=datetime(2022, 1, 1, tzinfo=timezone.utc), status=ComplaintStatus.CLOSED, complainant_name="test", reference_number="COMP-2022-0001", complaint_type=ComplaintType.OTHER, priority=ComplaintPriority.MEDIUM, created_by_id=1, updated_by_id=1),
    ])
    await test_session.commit()

    # Test default pagination and filtering
    response = await client.get("/api/v1/complaints/?status_filter=received", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2
    assert [item["title"] for item in data["items"]] == ["C2", "C1"]
