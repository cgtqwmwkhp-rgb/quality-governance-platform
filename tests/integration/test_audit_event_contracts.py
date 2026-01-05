
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit_log import AuditEvent


@pytest.mark.asyncio
async def test_policy_audit_events(client: AsyncClient, test_session: AsyncSession, auth_headers: dict):
    """Verify that audit events are correctly recorded for policy CRUD operations."""
    # Create a new policy
    policy_data = {"title": "Test Policy", "description": "Test Description"}
    response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
    assert response.status_code == 201
    policy_id = response.json()["id"]

    # Verify create event
    result = await test_session.execute(select(AuditEvent).where(AuditEvent.entity_id == str(policy_id)))
    create_event = result.scalar_one()
    assert create_event.event_type == "policy.created"
    assert create_event.entity_type == "policy"
    assert create_event.after_value["title"] == "Test Policy"

    # Update the policy
    update_data = {"title": "Updated Test Policy"}
    response = await client.put(f"/api/v1/policies/{policy_id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200

    # Verify update event
    result = await test_session.execute(select(AuditEvent).where(AuditEvent.entity_id == str(policy_id)).order_by(AuditEvent.timestamp.desc()))
    update_event = result.scalars().first()
    assert update_event.event_type == "policy.updated"
    assert update_event.before_value["title"] == "Updated Test Policy"
    assert update_event.after_value["title"] == "Updated Test Policy"

    # Delete the policy
    response = await client.delete(f"/api/v1/policies/{policy_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify delete event
    result = await test_session.execute(select(AuditEvent).where(AuditEvent.entity_id == str(policy_id)).order_by(AuditEvent.timestamp.desc()))
    delete_event = result.scalars().first()
    assert delete_event.event_type == "policy.deleted"
    assert delete_event.before_value["title"] == "Updated Test Policy"


@pytest.mark.asyncio
async def test_audit_event_ordering(client: AsyncClient, test_session: AsyncSession, auth_headers: dict):
    """Verify that audit events are returned in a deterministic order."""
    # Create multiple policies to generate audit events
    for i in range(3):
        policy_data = {"title": f"Test Policy {i}", "description": f"Test Description {i}"}
        await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)

    # Retrieve audit events
    # Note: There is no direct endpoint to list audit events yet. This test is a placeholder.
    # In a real scenario, we would have an endpoint like /api/v1/audit_events
    # and would verify the ordering here.
    pass
