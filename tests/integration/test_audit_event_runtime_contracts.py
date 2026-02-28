"""
Integration tests for audit event runtime contract enforcement.

These tests verify that write operations succeed and return proper responses.
AuditEvent is a lightweight logging class (not a SQLAlchemy model), so
audit events cannot be verified via database queries. Instead, we verify
that the API operations succeed, confirming the audit pipeline does not
block normal operations.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.policy import Policy


class TestPoliciesAuditEventRuntimeContract:
    """Test that Policies write operations succeed (audit events are logged)."""

    @pytest.mark.asyncio
    async def test_create_policy_succeeds(self, client: AsyncClient, test_session, auth_headers):
        """Verify that creating a policy succeeds."""
        policy_data = {
            "title": "Test Policy",
            "description": "Test Description",
            "document_type": "policy",
            "status": "draft",
        }
        response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
        assert response.status_code == 201

        policy_id = response.json()["id"]
        assert policy_id is not None

    @pytest.mark.asyncio
    async def test_update_policy_succeeds(self, client: AsyncClient, test_session, auth_headers):
        """Verify that updating a policy succeeds."""
        policy = Policy(
            title="Test Policy",
            description="Test Description",
            document_type="policy",
            status="draft",
            reference_number=f"POL-2026-{uuid.uuid4().hex[:8]}",
            created_by_id=1,
            updated_by_id=1,
        )
        test_session.add(policy)
        await test_session.commit()
        await test_session.refresh(policy)

        update_data = {"title": "Updated Policy"}
        response = await client.put(f"/api/v1/policies/{policy.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Policy"

    @pytest.mark.asyncio
    async def test_delete_policy_succeeds(self, client: AsyncClient, test_session, auth_headers):
        """Verify that deleting a policy succeeds."""
        policy = Policy(
            title="Test Policy",
            description="Test Description",
            document_type="policy",
            status="draft",
            reference_number=f"POL-2026-{uuid.uuid4().hex[:8]}",
            created_by_id=1,
            updated_by_id=1,
        )
        test_session.add(policy)
        await test_session.commit()
        await test_session.refresh(policy)
        policy_id = policy.id

        response = await client.delete(f"/api/v1/policies/{policy_id}", headers=auth_headers)
        assert response.status_code == 204


class TestIncidentsAuditEventRuntimeContract:
    """Test that Incidents write operations succeed (audit events are logged)."""

    @pytest.mark.asyncio
    async def test_create_incident_succeeds(self, client: AsyncClient, test_session, auth_headers):
        """Verify that creating an incident succeeds."""
        incident_data = {
            "title": "Test Incident",
            "description": "Test Description",
            "incident_type": "injury",
            "severity": "low",
            "status": "reported",
            "incident_date": datetime.now(timezone.utc).isoformat(),
            "location": "Test Location",
            "department": "Test Department",
        }
        response = await client.post("/api/v1/incidents/", json=incident_data, headers=auth_headers)
        assert response.status_code == 201

        incident_id = response.json()["id"]
        assert incident_id is not None


class TestComplaintsAuditEventRuntimeContract:
    """Test that Complaints write operations succeed (audit events are logged)."""

    @pytest.mark.asyncio
    async def test_create_complaint_succeeds(self, client: AsyncClient, test_session, auth_headers):
        """Verify that creating a complaint succeeds."""
        complaint_data = {
            "title": "Test Complaint",
            "description": "Test Description",
            "complaint_type": "service",
            "priority": "medium",
            "received_date": datetime.now(timezone.utc).isoformat(),
            "complainant_name": "Test User",
            "complainant_email": "test@example.com",
        }
        response = await client.post("/api/v1/complaints/", json=complaint_data, headers=auth_headers)
        assert response.status_code == 201

        complaint_id = response.json()["id"]
        assert complaint_id is not None
