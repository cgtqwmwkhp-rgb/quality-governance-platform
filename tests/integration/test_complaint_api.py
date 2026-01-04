"""Integration tests for Complaint API."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.complaint import Complaint, ComplaintStatus, ComplaintType
from src.domain.models.audit_log import AuditEvent


@pytest.mark.asyncio
async def test_create_complaint(client: AsyncClient, auth_headers: dict, test_session):
    """Test creating a complaint via API."""
    data = {
        "title": "Service Delay",
        "description": "The service was delayed by 2 hours.",
        "complaint_type": ComplaintType.SERVICE,
        "received_date": datetime.now().isoformat(),
        "complainant_name": "Jane Smith",
        "complainant_email": "jane@example.com",
    }
    response = await client.post("/api/v1/complaints/", json=data, headers=auth_headers)
    assert response.status_code == 201
    content = response.json()
    assert content["title"] == "Service Delay"
    assert content["reference_number"].startswith("COMP-")
    assert content["status"] == ComplaintStatus.RECEIVED

    # Verify audit log
    result = await test_session.execute(
        select(AuditEvent).where(
            AuditEvent.resource_type == "complaint",
            AuditEvent.event_type == "complaint.created"
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert int(event.resource_id) == content["id"]


@pytest.mark.asyncio
async def test_get_complaint_by_id(client: AsyncClient, auth_headers: dict, test_session):
    """Test getting a complaint by ID."""
    complaint = Complaint(
        title="Billing Error",
        description="Overcharged by $50.",
        received_date=datetime.now(),
        complainant_name="Bob Brown",
        reference_number="COMP-2026-0001",
    )
    test_session.add(complaint)
    await test_session.commit()
    await test_session.refresh(complaint)

    response = await client.get(f"/api/v1/complaints/{complaint.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Billing Error"


@pytest.mark.asyncio
async def test_list_complaints_deterministic_ordering(client: AsyncClient, auth_headers: dict, test_session):
    """Test listing complaints with deterministic ordering (received_date DESC, id ASC)."""
    now = datetime.now()
    c1 = Complaint(title="C1", description="D1", received_date=now - timedelta(days=1), complainant_name="N1", reference_number="REF1")
    c2 = Complaint(title="C2", description="D2", received_date=now, complainant_name="N2", reference_number="REF2")
    c3 = Complaint(title="C3", description="D3", received_date=now, complainant_name="N3", reference_number="REF3")
    
    test_session.add_all([c1, c2, c3])
    await test_session.commit()

    response = await client.get("/api/v1/complaints/", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    
    # Ordering: received_date DESC, then id ASC
    # c2 and c3 have same received_date, so c2 (smaller id) should come before c3 if created first, 
    # but wait, id ASC means smaller id first.
    ids = [item["id"] for item in items]
    assert ids[0] < ids[1] # c2 and c3
    assert items[2]["title"] == "C1" # c1 is oldest


@pytest.mark.asyncio
async def test_update_complaint_status(client: AsyncClient, auth_headers: dict, test_session):
    """Test updating complaint status and recording audit log."""
    complaint = Complaint(
        title="Delivery Issue",
        description="Package lost.",
        received_date=datetime.now(),
        complainant_name="Alice Green",
        reference_number="COMP-2026-0002",
        status=ComplaintStatus.RECEIVED
    )
    test_session.add(complaint)
    await test_session.commit()
    await test_session.refresh(complaint)

    data = {"status": ComplaintStatus.RESOLVED, "resolution_summary": "Found and delivered."}
    response = await client.patch(f"/api/v1/complaints/{complaint.id}", json=data, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == ComplaintStatus.RESOLVED

    # Verify audit log
    result = await test_session.execute(
        select(AuditEvent).where(
            AuditEvent.resource_type == "complaint",
            AuditEvent.event_type == "complaint.updated"
        )
    )
    event = result.scalars().all()[-1] # Get latest
    assert event.payload["new_status"] == ComplaintStatus.RESOLVED
    assert event.payload["old_status"] == ComplaintStatus.RECEIVED
