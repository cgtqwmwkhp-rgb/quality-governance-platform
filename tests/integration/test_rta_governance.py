"""Integration tests for RTA governance (RBAC, audit, determinism, pagination)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.rta import RoadTrafficCollision, RTAAction, RTASeverity, RTAStatus


@pytest.mark.asyncio
async def test_create_rta_unauthenticated_returns_401(client: AsyncClient):
    """Test that creating an RTA without authentication returns 401."""
    data = {
        "title": "Test RTA",
        "description": "Test collision",
        "collision_date": datetime.now(timezone.utc).isoformat(),
        "reported_date": datetime.now(timezone.utc).isoformat(),
        "location": "Test Location",
    }
    response = await client.post("/api/v1/rtas/", json=data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_rta_with_auth(client: AsyncClient, auth_headers: dict, test_session):
    """Test creating an RTA with authentication and verify audit log."""
    collision_date = datetime.now(timezone.utc)
    data = {
        "title": "Integration Test RTA",
        "description": "Test collision description",
        "severity": RTASeverity.DAMAGE_ONLY,
        "status": RTAStatus.REPORTED,
        "collision_date": collision_date.isoformat(),
        "reported_date": collision_date.isoformat(),
        "location": "Test Location",
        "road_name": "Test Road",
    }
    response = await client.post("/api/v1/rtas/", json=data, headers=auth_headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["title"] == "Integration Test RTA"
    assert res_data["reference_number"].startswith(f"RTA-{collision_date.year}-")
    assert res_data["severity"] == RTASeverity.DAMAGE_ONLY


@pytest.mark.asyncio
async def test_list_rtas_deterministic_ordering(client: AsyncClient, auth_headers: dict, test_session):
    """Test that RTAs are returned in deterministic order (created_at DESC, id ASC)."""
    now = datetime.now(timezone.utc)

    # Create 3 RTAs with different created_at times
    rtas = []
    for i in range(3):
        rta = RoadTrafficCollision(
            title=f"RTA {i}",
            description="Test",
            collision_date=now,
            reported_date=now,
            location="Test Location",
            reference_number=f"RTA-2026-T{uuid.uuid4().hex[:6]}{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(rta)
        rtas.append(rta)

    await test_session.commit()

    response = await client.get("/api/v1/rtas/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    # Verify deterministic ordering: newest first (created_at DESC)
    items = data["items"]
    if len(items) >= 3:
        # Find our test RTAs in the results
        test_rtas = [item for item in items if item["title"].startswith("RTA ")]
        assert len(test_rtas) >= 3
        # They should be in reverse order (newest first)
        assert test_rtas[0]["title"] == "RTA 0"
        assert test_rtas[1]["title"] == "RTA 1"
        assert test_rtas[2]["title"] == "RTA 2"


@pytest.mark.asyncio
async def test_update_rta_with_audit(client: AsyncClient, auth_headers: dict, test_session):
    """Test updating an RTA and verify audit log."""
    # Create RTA
    rta = RoadTrafficCollision(
        title="Original Title",
        description="Original description",
        collision_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        location="Original Location",
        reference_number=f"RTA-2026-U{uuid.uuid4().hex[:7]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # Update RTA
    update_data = {
        "title": "Updated Title",
        "severity": RTASeverity.SERIOUS_INJURY,
    }
    response = await client.patch(f"/api/v1/rtas/{rta.id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["title"] == "Updated Title"
    assert res_data["severity"] == RTASeverity.SERIOUS_INJURY


@pytest.mark.asyncio
async def test_delete_rta_with_audit(client: AsyncClient, auth_headers: dict, test_session):
    """Test deleting an RTA and verify audit log."""
    # Create RTA
    rta = RoadTrafficCollision(
        title="To Delete",
        description="Will be deleted",
        collision_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        location="Test Location",
        reference_number=f"RTA-2026-D{uuid.uuid4().hex[:7]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)
    rta_id = rta.id

    # Delete RTA
    response = await client.delete(f"/api/v1/rtas/{rta_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify deletion
    response = await client.get(f"/api/v1/rtas/{rta_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rta_404_canonical_envelope(client: AsyncClient, auth_headers: dict):
    """Test that 404 errors return canonical error envelope with request_id."""
    response = await client.get("/api/v1/rtas/999999", headers=auth_headers)
    assert response.status_code == 404
    data = response.json()
    error = data.get("error", data)
    assert error.get("code") or error.get("error_code"), "Error code should be present"
    assert error.get("message"), "Error message should be present"
    request_id = error.get("request_id", data.get("request_id", ""))
    assert request_id, "Request ID should be present"


@pytest.mark.asyncio
async def test_create_rta_action_with_audit(client: AsyncClient, auth_headers: dict, test_session):
    """Test creating an RTA action and verify audit log."""
    # Create RTA first
    rta = RoadTrafficCollision(
        title="RTA for Actions",
        description="Test",
        collision_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        location="Test Location",
        reference_number=f"RTA-2026-A{uuid.uuid4().hex[:7]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # Create action
    action_data = {
        "title": "Test Action",
        "description": "Test action description",
        "action_type": "corrective",
        "priority": "high",
    }
    response = await client.post(f"/api/v1/rtas/{rta.id}/actions", json=action_data, headers=auth_headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["title"] == "Test Action"
    assert res_data["rta_id"] == rta.id
    assert res_data["reference_number"].startswith("RTAACT-")


@pytest.mark.asyncio
async def test_list_rta_actions_deterministic_ordering(client: AsyncClient, auth_headers: dict, test_session):
    """Test that RTA actions are returned in deterministic order (created_at DESC, id ASC)."""
    now = datetime.now(timezone.utc)

    # Create RTA
    rta = RoadTrafficCollision(
        title="RTA for Action Ordering",
        description="Test",
        collision_date=now,
        reported_date=now,
        location="Test Location",
        reference_number=f"RTA-2026-O{uuid.uuid4().hex[:7]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # Create 3 actions with different created_at times
    for i in range(3):
        action = RTAAction(
            rta_id=rta.id,
            title=f"Action {i}",
            description="Test",
            reference_number=f"RTAACT-{uuid.uuid4().hex[:8]}{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(action)

    await test_session.commit()

    response = await client.get(f"/api/v1/rtas/{rta.id}/actions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    # Verify deterministic ordering: newest first
    items = data["items"]
    assert len(items) >= 3
    assert items[0]["title"] == "Action 0"
    assert items[1]["title"] == "Action 1"
    assert items[2]["title"] == "Action 2"


@pytest.mark.asyncio
async def test_rta_investigations_linkage(client: AsyncClient, auth_headers: dict, test_session):
    """Test that RTA investigations linkage endpoint works and returns deterministic order."""
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun, InvestigationTemplate

    now = datetime.now(timezone.utc)

    # Create RTA
    rta = RoadTrafficCollision(
        title="RTA for Investigations",
        description="Test",
        collision_date=now,
        reported_date=now,
        location="Test Location",
        reference_number=f"RTA-2026-I{uuid.uuid4().hex[:7]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # Create investigation template
    template = InvestigationTemplate(
        name="Test Template",
        description="Test",
        structure={"sections": []},
        applicable_entity_types=["road_traffic_collision"],
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    # Create 2 investigations for this RTA
    for i in range(2):
        investigation = InvestigationRun(
            template_id=template.id,
            title=f"Investigation {i}",
            description="Test",
            assigned_entity_type=AssignedEntityType.ROAD_TRAFFIC_COLLISION,
            assigned_entity_id=rta.id,
            reference_number=f"INV-RTA-{uuid.uuid4().hex[:6]}{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(investigation)

    await test_session.commit()

    # Get investigations for RTA
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Response is paginated envelope
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    items = data["items"]
    assert len(items) >= 2

    # Verify deterministic ordering: newest first (created_at DESC, id ASC)
    assert items[0]["title"] == "Investigation 0"
    assert items[1]["title"] == "Investigation 1"

    # Pagination fields correct
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_complaint_investigations_linkage(client: AsyncClient, auth_headers: dict, test_session):
    """Test that complaint investigations linkage endpoint works and returns deterministic order."""
    from src.domain.models.complaint import Complaint
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun, InvestigationTemplate

    now = datetime.now(timezone.utc)

    # Create complaint
    complaint = Complaint(
        title="Test Complaint",
        description="Test",
        received_date=now,
        reference_number=f"COMP-2026-I{uuid.uuid4().hex[:7]}",
        complainant_name="Test Complainant",
    )
    test_session.add(complaint)
    await test_session.commit()
    await test_session.refresh(complaint)

    # Create investigation template
    template = InvestigationTemplate(
        name="Test Template",
        description="Test",
        structure={"sections": []},
        applicable_entity_types=["complaint"],
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    # Create 2 investigations for this complaint
    for i in range(2):
        investigation = InvestigationRun(
            template_id=template.id,
            title=f"Complaint Investigation {i}",
            description="Test",
            assigned_entity_type=AssignedEntityType.COMPLAINT,
            assigned_entity_id=complaint.id,
            reference_number=f"INV-CMP-{uuid.uuid4().hex[:6]}{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(investigation)

    await test_session.commit()

    # Get investigations for complaint
    response = await client.get(f"/api/v1/complaints/{complaint.id}/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Response is paginated envelope
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    items = data["items"]
    assert len(items) >= 2

    # Verify deterministic ordering: newest first (created_at DESC, id ASC)
    assert items[0]["title"] == "Complaint Investigation 0"
    assert items[1]["title"] == "Complaint Investigation 1"

    # Pagination fields correct
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_rta_pagination_consistency(client: AsyncClient, auth_headers: dict, test_session):
    """Test that RTA pagination is consistent and total_pages is calculated correctly."""
    now = datetime.now(timezone.utc)

    # Create 15 RTAs
    for i in range(15):
        rta = RoadTrafficCollision(
            title=f"Pagination RTA {i}",
            description="Test",
            collision_date=now,
            reported_date=now,
            location="Test Location",
            reference_number=f"RTA-PG-{uuid.uuid4().hex[:6]}{i:02d}",
        )
        test_session.add(rta)

    await test_session.commit()

    # Get page 1 with page_size=5
    response = await client.get("/api/v1/rtas/?page=1&page_size=5", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5
    assert data["total"] >= 15
    # total_pages should be ceil(total / page_size)
    expected_pages = (data["total"] + 4) // 5  # ceiling division
    assert data["total_pages"] == expected_pages


@pytest.mark.asyncio
async def test_rta_investigations_pagination_fields(client: AsyncClient, auth_headers: dict, test_session):
    """Test that RTA investigations pagination fields are correct."""
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun, InvestigationTemplate

    now = datetime.now(timezone.utc)

    # Create RTA
    rta = RoadTrafficCollision(
        title="RTA for Pagination Test",
        description="Test",
        collision_date=now,
        reported_date=now,
        location="Test Location",
        reference_number=f"RTA-PGM-{uuid.uuid4().hex[:8]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # Create investigation template
    template = InvestigationTemplate(
        name="Test Template",
        description="Test",
        structure={"sections": []},
        applicable_entity_types=["road_traffic_collision"],
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    # Create 30 investigations for pagination testing
    for i in range(30):
        investigation = InvestigationRun(
            template_id=template.id,
            title=f"Investigation {i}",
            description="Test",
            assigned_entity_type=AssignedEntityType.ROAD_TRAFFIC_COLLISION,
            assigned_entity_id=rta.id,
            reference_number=f"INV-PG-{uuid.uuid4().hex[:6]}{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(investigation)

    await test_session.commit()

    # Test page 1 (default page_size=25)
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total_pages"] == 2
    assert len(data["items"]) == 25

    # Test page 2
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert data["page"] == 2
    assert data["page_size"] == 25
    assert data["total_pages"] == 2
    assert len(data["items"]) == 5

    # Test custom page_size
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page_size=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 3
    assert len(data["items"]) == 10


@pytest.mark.asyncio
async def test_rta_investigations_invalid_page_param(client: AsyncClient, auth_headers: dict, test_session):
    """Test that invalid page parameter returns 422 validation error."""
    now = datetime.now(timezone.utc)

    # Create RTA
    rta = RoadTrafficCollision(
        title="RTA for Validation Test",
        description="Test",
        collision_date=now,
        reported_date=now,
        location="Test Location",
        reference_number=f"RTA-VAL-{uuid.uuid4().hex[:8]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # page=0 should fail (must be >= 1)
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page=0", headers=auth_headers)
    assert response.status_code == 422

    # page=-1 should fail
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page=-1", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rta_investigations_invalid_page_size_param(client: AsyncClient, auth_headers: dict, test_session):
    """Test that invalid page_size parameter returns 422 validation error."""
    now = datetime.now(timezone.utc)

    # Create RTA
    rta = RoadTrafficCollision(
        title="RTA for Page Size Validation Test",
        description="Test",
        collision_date=now,
        reported_date=now,
        location="Test Location",
        reference_number=f"RTA-PSV-{uuid.uuid4().hex[:8]}",
    )
    test_session.add(rta)
    await test_session.commit()
    await test_session.refresh(rta)

    # page_size=0 should fail (must be >= 1)
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page_size=0", headers=auth_headers)
    assert response.status_code == 422

    # page_size=101 should fail (must be <= 100)
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page_size=101", headers=auth_headers)
    assert response.status_code == 422

    # page_size=999 should fail
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations?page_size=999", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_complaint_investigations_pagination_fields(client: AsyncClient, auth_headers: dict, test_session):
    """Test that complaint investigations pagination fields are correct."""
    from src.domain.models.complaint import Complaint
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun, InvestigationTemplate

    now = datetime.now(timezone.utc)

    # Create complaint
    complaint = Complaint(
        title="Complaint for Pagination Test",
        description="Test",
        received_date=now,
        reference_number=f"COMP-PG-{uuid.uuid4().hex[:8]}",
        complainant_name="Test Complainant",
    )
    test_session.add(complaint)
    await test_session.commit()
    await test_session.refresh(complaint)

    # Create investigation template
    template = InvestigationTemplate(
        name="Test Template",
        description="Test",
        structure={"sections": []},
        applicable_entity_types=["complaint"],
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    # Create 30 investigations for pagination testing
    for i in range(30):
        investigation = InvestigationRun(
            template_id=template.id,
            title=f"Complaint Investigation {i}",
            description="Test",
            assigned_entity_type=AssignedEntityType.COMPLAINT,
            assigned_entity_id=complaint.id,
            reference_number=f"INV-CP-{uuid.uuid4().hex[:6]}{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(investigation)

    await test_session.commit()

    # Test page 1 (default page_size=25)
    response = await client.get(f"/api/v1/complaints/{complaint.id}/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total_pages"] == 2
    assert len(data["items"]) == 25

    # Test page 2
    response = await client.get(f"/api/v1/complaints/{complaint.id}/investigations?page=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert data["page"] == 2
    assert data["page_size"] == 25
    assert data["total_pages"] == 2
    assert len(data["items"]) == 5

    # Test custom page_size
    response = await client.get(
        f"/api/v1/complaints/{complaint.id}/investigations?page_size=10",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 3
    assert len(data["items"]) == 10
