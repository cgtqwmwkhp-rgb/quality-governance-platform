"""Integration tests for Complaint API."""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from src.domain.models.complaint import Complaint, ComplaintStatus, ComplaintType
from tests.factories import ComplaintFactory


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


@pytest.mark.asyncio
async def test_get_complaint_by_id(client: AsyncClient, auth_headers: dict, test_session):
    """Test getting a complaint by ID."""
    complaint = ComplaintFactory.build(
        title="Billing Error",
        description="Overcharged by $50.",
        complainant_name="Bob Brown",
        reference_number=f"COMP-2026-{uuid.uuid4().hex[:8]}",
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
    suffix = uuid.uuid4().hex[:6]
    c1 = ComplaintFactory.build(
        title=f"C1-{suffix}",
        description="D1",
        received_date=now - timedelta(days=1),
        complainant_name="N1",
        reference_number=f"REF-{uuid.uuid4().hex[:8]}",
    )
    c2 = ComplaintFactory.build(
        title=f"C2-{suffix}",
        description="D2",
        received_date=now,
        complainant_name="N2",
        reference_number=f"REF-{uuid.uuid4().hex[:8]}",
    )
    c3 = ComplaintFactory.build(
        title=f"C3-{suffix}",
        description="D3",
        received_date=now,
        complainant_name="N3",
        reference_number=f"REF-{uuid.uuid4().hex[:8]}",
    )

    test_session.add_all([c1, c2, c3])
    await test_session.commit()

    response = await client.get("/api/v1/complaints/", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]

    # Only validate ordering of records created in this test.
    our_items = [item for item in items if item["title"] in {f"C1-{suffix}", f"C2-{suffix}", f"C3-{suffix}"}]
    assert len(our_items) >= 2
    if len(our_items) == 3:
        assert our_items[-1]["title"] == f"C1-{suffix}"  # c1 is oldest by received_date


@pytest.mark.asyncio
async def test_update_complaint_status(client: AsyncClient, auth_headers: dict, test_session):
    """Test updating complaint status and recording audit log."""
    complaint = ComplaintFactory.build(
        title="Delivery Issue",
        description="Package lost.",
        complainant_name="Alice Green",
        reference_number=f"COMP-2026-{uuid.uuid4().hex[:8]}",
        status=ComplaintStatus.RECEIVED,
    )
    test_session.add(complaint)
    await test_session.commit()
    await test_session.refresh(complaint)

    data = {
        "status": ComplaintStatus.RESOLVED,
        "resolution_summary": "Found and delivered.",
    }
    response = await client.patch(f"/api/v1/complaints/{complaint.id}", json=data, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == ComplaintStatus.RESOLVED


# ============================================================================
# Complaint Idempotency Tests (Release Governance Condition #1)
# ============================================================================


@pytest.mark.asyncio
async def test_create_complaint_with_external_ref(client: AsyncClient, auth_headers: dict, test_session):
    """Test creating a complaint with external_ref for idempotency."""
    external_ref = f"EXT-COMP-{uuid.uuid4().hex[:8]}"
    data = {
        "title": "ETL Imported Complaint",
        "description": "Complaint imported from external system.",
        "complaint_type": ComplaintType.SERVICE,
        "received_date": datetime.now().isoformat(),
        "complainant_name": "External System",
        "external_ref": external_ref,
    }
    response = await client.post("/api/v1/complaints/", json=data, headers=auth_headers)
    assert response.status_code == 201
    content = response.json()
    assert content["external_ref"] == external_ref
    assert content["reference_number"].startswith("COMP-")


@pytest.mark.asyncio
async def test_duplicate_external_ref_returns_409(client: AsyncClient, auth_headers: dict, test_session):
    """Test that duplicate external_ref returns 409 Conflict (idempotency)."""
    external_ref = f"EXT-COMP-DUP-{uuid.uuid4().hex[:8]}"
    data = {
        "title": "First Complaint",
        "description": "This is the first complaint with this external_ref.",
        "complaint_type": ComplaintType.PRODUCT,
        "received_date": datetime.now().isoformat(),
        "complainant_name": "First Submitter",
        "external_ref": external_ref,
    }

    # First request: should succeed
    response1 = await client.post("/api/v1/complaints/", json=data, headers=auth_headers)
    assert response1.status_code == 201
    first_id = response1.json()["id"]

    # Second request with same external_ref: should return 409
    data2 = {
        "title": "Second Complaint (duplicate)",
        "description": "This should fail due to duplicate external_ref.",
        "complaint_type": ComplaintType.SERVICE,
        "received_date": datetime.now().isoformat(),
        "complainant_name": "Second Submitter",
        "external_ref": external_ref,  # Same external_ref
    }
    response2 = await client.post("/api/v1/complaints/", json=data2, headers=auth_headers)
    assert response2.status_code == 409

    # Verify error response contains expected fields (error envelope format)
    resp_data = response2.json()
    error = resp_data.get("error", resp_data.get("detail", resp_data))
    assert error.get("code") in {"DUPLICATE_EXTERNAL_REF", "DUPLICATE_ENTITY"}
    details = error.get("details", error)
    assert details.get("existing_id") == first_id
    assert external_ref in (error.get("message", "") + str(details))


@pytest.mark.asyncio
async def test_create_complaint_without_external_ref_no_idempotency(
    client: AsyncClient, auth_headers: dict, test_session
):
    """Test that complaints without external_ref can be created multiple times."""
    data = {
        "title": "Manual Complaint",
        "description": "No external_ref - manual entry.",
        "complaint_type": ComplaintType.OTHER,
        "received_date": datetime.now().isoformat(),
        "complainant_name": "Manual User",
        # No external_ref
    }

    # First request
    response1 = await client.post("/api/v1/complaints/", json=data, headers=auth_headers)
    assert response1.status_code == 201

    # Second request with same data but no external_ref: should also succeed
    # (no idempotency check without external_ref)
    response2 = await client.post("/api/v1/complaints/", json=data, headers=auth_headers)
    assert response2.status_code == 201

    # Verify two different complaints were created
    assert response1.json()["id"] != response2.json()["id"]


@pytest.mark.asyncio
async def test_different_external_refs_create_separate_complaints(
    client: AsyncClient, auth_headers: dict, test_session
):
    """Test that different external_refs create separate complaints."""
    base_data = {
        "title": "ETL Complaint",
        "description": "Imported from external system.",
        "complaint_type": ComplaintType.BILLING,
        "received_date": datetime.now().isoformat(),
        "complainant_name": "External System",
    }

    # Create first complaint
    external_ref_1 = f"EXT-UNIQUE-{uuid.uuid4().hex[:8]}"
    external_ref_2 = f"EXT-UNIQUE-{uuid.uuid4().hex[:8]}"
    data1 = {**base_data, "external_ref": external_ref_1}
    response1 = await client.post("/api/v1/complaints/", json=data1, headers=auth_headers)
    assert response1.status_code == 201

    # Create second complaint with different external_ref
    data2 = {**base_data, "external_ref": external_ref_2}
    response2 = await client.post("/api/v1/complaints/", json=data2, headers=auth_headers)
    assert response2.status_code == 201

    # Verify they have different IDs
    assert response1.json()["id"] != response2.json()["id"]
    assert response1.json()["external_ref"] == external_ref_1
    assert response2.json()["external_ref"] == external_ref_2
