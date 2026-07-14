"""CUJ-OPS-INTAKE-TRIAGE: unassigned intake → assign owner → notify → action assign."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.notification import Assignment, Notification, NotificationType


@pytest.mark.asyncio
async def test_ops_intake_triage_incident_owner_and_action_notify(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_session: AsyncSession,
) -> None:
    """Portal-like incident starts unassigned; PATCH owner notifies; action assign notifies."""
    incident_payload = {
        "title": "CUJ triage wet floor intake",
        "description": "Portal submission with no case owner",
        "incident_type": "injury",
        "severity": "medium",
        "status": "reported",
        "incident_date": datetime.now(timezone.utc).isoformat(),
        "location": "Warehouse",
    }
    create_resp = await client.post("/api/v1/incidents/", json=incident_payload, headers=auth_headers)
    assert create_resp.status_code == 201, create_resp.text
    incident = create_resp.json()
    incident_id = incident["id"]
    assert incident.get("owner_id") in (None, 0) or incident.get("owner_id") is None

    unassigned = await client.get(
        "/api/v1/incidents/",
        params={"owner": "unassigned", "page": 1, "page_size": 50},
        headers=auth_headers,
    )
    assert unassigned.status_code == 200, unassigned.text
    unassigned_ids = {item["id"] for item in unassigned.json()["items"]}
    assert incident_id in unassigned_ids

    assign_resp = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={"owner_id": 1},
        headers=auth_headers,
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["owner_id"] == 1

    still_unassigned = await client.get(
        "/api/v1/incidents/",
        params={"owner": "unassigned", "page": 1, "page_size": 50},
        headers=auth_headers,
    )
    assert still_unassigned.status_code == 200
    assert incident_id not in {item["id"] for item in still_unassigned.json()["items"]}

    test_session.expire_all()
    assignment = await test_session.scalar(
        select(Assignment).where(
            Assignment.entity_type == "incident",
            Assignment.entity_id == str(incident_id),
            Assignment.assigned_to_user_id == 1,
        )
    )
    assert assignment is not None

    notification = await test_session.scalar(
        select(Notification).where(
            Notification.user_id == 1,
            Notification.type == NotificationType.ASSIGNMENT,
            Notification.entity_type == "incident",
            Notification.entity_id == str(incident_id),
        )
    )
    assert notification is not None

    action_resp = await client.post(
        "/api/v1/actions/",
        json={
            "title": "CUJ triage first action",
            "description": "Owner follow-up after triage",
            "source_type": "incident",
            "source_id": incident_id,
            "priority": "high",
            "assigned_to_email": "test@example.com",
        },
        headers=auth_headers,
    )
    assert action_resp.status_code == 201, action_resp.text
    action = action_resp.json()
    assert action.get("owner_id") == 1 or action.get("assigned_to_email") == "test@example.com"

    test_session.expire_all()
    action_notify = await test_session.scalar(
        select(Notification).where(
            Notification.user_id == 1,
            Notification.type == NotificationType.ASSIGNMENT,
            Notification.entity_type == "action",
            Notification.entity_id == str(action["id"]),
        )
    )
    assert action_notify is not None

    bad_email = await client.post(
        "/api/v1/actions/",
        json={
            "title": "CUJ bad assignee must fail",
            "description": "Must not create unowned",
            "source_type": "incident",
            "source_id": incident_id,
            "priority": "medium",
            "assigned_to_email": "nobody-not-in-tenant@example.com",
        },
        headers=auth_headers,
    )
    assert bad_email.status_code == 400, bad_email.text
    assert "not found" in bad_email.text.lower() or "unowned" in bad_email.text.lower()


@pytest.mark.asyncio
async def test_ops_intake_triage_complaint_unassigned_and_owner_patch(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_session: AsyncSession,
) -> None:
    """Complaint intakes support owner=unassigned and PATCH owner_id notify."""
    payload = {
        "title": "CUJ triage complaint intake",
        "description": "Portal complaint without owner",
        "complaint_type": "service",
        "priority": "medium",
        "received_date": datetime.now(timezone.utc).isoformat(),
        "complainant_name": "Portal User",
        "complainant_email": "portal.user@example.com",
    }
    create_resp = await client.post("/api/v1/complaints/", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201, create_resp.text
    complaint = create_resp.json()
    complaint_id = complaint["id"]
    assert complaint.get("owner_id") is None

    unassigned = await client.get(
        "/api/v1/complaints/",
        params={"owner": "unassigned", "page": 1, "page_size": 50},
        headers=auth_headers,
    )
    assert unassigned.status_code == 200, unassigned.text
    assert complaint_id in {item["id"] for item in unassigned.json()["items"]}

    bad_owner = await client.patch(
        f"/api/v1/complaints/{complaint_id}",
        json={"owner_id": 999999},
        headers=auth_headers,
    )
    assert bad_owner.status_code == 400, bad_owner.text

    assign_resp = await client.patch(
        f"/api/v1/complaints/{complaint_id}",
        json={"owner_id": 1},
        headers=auth_headers,
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["owner_id"] == 1

    test_session.expire_all()
    notification = await test_session.scalar(
        select(Notification).where(
            Notification.user_id == 1,
            Notification.type == NotificationType.ASSIGNMENT,
            Notification.entity_type == "complaint",
            Notification.entity_id == str(complaint_id),
        )
    )
    assert notification is not None
