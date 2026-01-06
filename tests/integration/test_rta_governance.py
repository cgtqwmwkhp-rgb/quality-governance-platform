"""Integration tests for RTA governance (RBAC, audit, determinism, pagination)."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditEvent
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

    # Check audit log
    audit_result = await test_session.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "rta", AuditEvent.action == "create")
        .order_by(AuditEvent.created_at.desc())
    )
    audit_log = audit_result.scalars().first()
    assert audit_log is not None
    assert audit_log.entity_id == str(res_data["id"])
    assert audit_log.event_type == "rta.created"
    assert audit_log.request_id is not None
    assert audit_log.request_id != ""


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
            reference_number=f"RTA-2026-TEST{i}",
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
        reference_number="RTA-2026-UPDATE",
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

    # Check audit log
    audit_result = await test_session.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "rta", AuditEvent.action == "update", AuditEvent.entity_id == str(rta.id))
        .order_by(AuditEvent.created_at.desc())
    )
    audit_log = audit_result.scalars().first()
    assert audit_log is not None
    assert audit_log.event_type == "rta.updated"
    assert audit_log.request_id is not None
    assert audit_log.request_id != ""


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
        reference_number="RTA-2026-DELETE",
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

    # Check audit log
    audit_result = await test_session.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "rta", AuditEvent.action == "delete", AuditEvent.entity_id == str(rta_id))
        .order_by(AuditEvent.created_at.desc())
    )
    audit_log = audit_result.scalars().first()
    assert audit_log is not None
    assert audit_log.event_type == "rta.deleted"
    assert audit_log.request_id is not None
    assert audit_log.request_id != ""


@pytest.mark.asyncio
async def test_rta_404_canonical_envelope(client: AsyncClient, auth_headers: dict):
    """Test that 404 errors return canonical error envelope with request_id."""
    response = await client.get("/api/v1/rtas/999999", headers=auth_headers)
    assert response.status_code == 404
    data = response.json()
    assert "error_code" in data
    assert "message" in data
    assert "request_id" in data
    assert data["request_id"] is not None
    assert data["request_id"] != ""


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
        reference_number="RTA-2026-ACTIONS",
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

    # Check audit log
    audit_result = await test_session.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "rta_action", AuditEvent.action == "create")
        .order_by(AuditEvent.created_at.desc())
    )
    audit_log = audit_result.scalars().first()
    assert audit_log is not None
    assert audit_log.entity_id == str(res_data["id"])
    assert audit_log.event_type == "rta_action.created"
    assert audit_log.request_id is not None
    assert audit_log.request_id != ""


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
        reference_number="RTA-2026-ORDER",
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
            reference_number=f"RTAACT-2026-TEST{i}",
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
        reference_number="RTA-2026-INV",
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
            reference_number=f"INV-2026-RTA{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(investigation)

    await test_session.commit()

    # Get investigations for RTA
    response = await client.get(f"/api/v1/rtas/{rta.id}/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Verify deterministic ordering: newest first
    assert data[0]["title"] == "Investigation 0"
    assert data[1]["title"] == "Investigation 1"


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
        reference_number="COMP-2026-INV",
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
            reference_number=f"INV-2026-COMP{i}",
            created_at=now - timedelta(minutes=i),
        )
        test_session.add(investigation)

    await test_session.commit()

    # Get investigations for complaint
    response = await client.get(f"/api/v1/complaints/{complaint.id}/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Verify deterministic ordering: newest first
    assert data[0]["title"] == "Complaint Investigation 0"
    assert data[1]["title"] == "Complaint Investigation 1"


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
            reference_number=f"RTA-2026-PAGE{i:02d}",
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
