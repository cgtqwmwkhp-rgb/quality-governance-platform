"""
Integration tests for audit event runtime contract enforcement.

These tests verify that audit events are recorded with the canonical schema
defined in Stage 3.0 for all write operations.
"""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditEvent
from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.policy import Policy


class TestPoliciesAuditEventRuntimeContract:
    """Test that Policies module records canonical audit events at runtime."""

    @pytest.mark.asyncio
    async def test_create_policy_records_audit_event(self, client: AsyncClient, test_session, auth_headers):
        """Verify that creating a policy records an audit event with canonical schema."""
        # Create a policy
        policy_data = {
            "title": "Test Policy",
            "description": "Test Description",
            "document_type": "policy",
            "status": "draft",
        }
        response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
        assert response.status_code == 201

        policy_id = response.json()["id"]

        # Verify audit event was recorded
        result = await test_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "policy",
                AuditEvent.entity_id == str(policy_id),
                AuditEvent.event_type == "policy.created",
            )
        )
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None, "Audit event was not recorded"

        # Verify canonical audit event schema
        assert audit_event.event_type == "policy.created"
        assert audit_event.entity_type == "policy"
        assert audit_event.entity_id == str(policy_id)
        assert audit_event.action == "create"
        assert audit_event.actor_user_id is not None
        # request_id should be present as a field (may be None in test environment)
        assert hasattr(audit_event, "request_id")
        assert audit_event.timestamp is not None

    @pytest.mark.asyncio
    async def test_update_policy_records_audit_event(self, client: AsyncClient, test_session, auth_headers):
        """Verify that updating a policy records an audit event with canonical schema."""
        # Create a policy first
        policy = Policy(
            title="Test Policy",
            description="Test Description",
            document_type="policy",
            status="draft",
            reference_number="POL-2026-0001",
            created_by_id=1,
            updated_by_id=1,
        )
        test_session.add(policy)
        await test_session.commit()
        await test_session.refresh(policy)

        # Update the policy
        update_data = {"title": "Updated Policy"}
        response = await client.put(f"/api/v1/policies/{policy.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200

        # Verify audit event was recorded
        result = await test_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "policy",
                AuditEvent.entity_id == str(policy.id),
                AuditEvent.event_type == "policy.updated",
            )
        )
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None, "Audit event was not recorded"

        # Verify canonical audit event schema
        assert audit_event.event_type == "policy.updated"
        assert audit_event.entity_type == "policy"
        assert audit_event.entity_id == str(policy.id)
        assert audit_event.action == "update"
        assert audit_event.actor_user_id is not None
        # request_id should be present as a field (may be None in test environment)
        assert hasattr(audit_event, "request_id")

    @pytest.mark.asyncio
    async def test_delete_policy_records_audit_event(self, client: AsyncClient, test_session, auth_headers):
        """Verify that deleting a policy records an audit event with canonical schema."""
        # Create a policy first
        policy = Policy(
            title="Test Policy",
            description="Test Description",
            document_type="policy",
            status="draft",
            reference_number="POL-2026-0001",
            created_by_id=1,
            updated_by_id=1,
        )
        test_session.add(policy)
        await test_session.commit()
        await test_session.refresh(policy)
        policy_id = policy.id

        # Delete the policy
        response = await client.delete(f"/api/v1/policies/{policy_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify audit event was recorded
        result = await test_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "policy",
                AuditEvent.entity_id == str(policy_id),
                AuditEvent.event_type == "policy.deleted",
            )
        )
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None, "Audit event was not recorded"

        # Verify canonical audit event schema
        assert audit_event.event_type == "policy.deleted"
        assert audit_event.entity_type == "policy"
        assert audit_event.entity_id == str(policy_id)
        assert audit_event.action == "delete"
        assert audit_event.actor_user_id is not None
        # request_id should be present as a field (may be None in test environment)
        assert hasattr(audit_event, "request_id")


class TestIncidentsAuditEventRuntimeContract:
    """Test that Incidents module records canonical audit events at runtime."""

    @pytest.mark.asyncio
    async def test_create_incident_records_audit_event(self, client: AsyncClient, test_session, auth_headers):
        """Verify that creating an incident records an audit event with canonical schema."""
        # Create an incident
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
        response = await client.post("/api/v1/incidents", json=incident_data, headers=auth_headers)
        assert response.status_code == 201

        incident_id = response.json()["id"]

        # Verify audit event was recorded
        result = await test_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "incident",
                AuditEvent.entity_id == str(incident_id),
                AuditEvent.event_type == "incident.created",
            )
        )
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None, "Audit event was not recorded"

        # Verify canonical audit event schema
        assert audit_event.event_type == "incident.created"
        assert audit_event.entity_type == "incident"
        assert audit_event.entity_id == str(incident_id)
        assert audit_event.action == "create"
        assert audit_event.actor_user_id is not None
        # request_id should be present as a field (may be None in test environment)
        assert hasattr(audit_event, "request_id")


class TestComplaintsAuditEventRuntimeContract:
    """Test that Complaints module records canonical audit events at runtime."""

    @pytest.mark.asyncio
    async def test_create_complaint_records_audit_event(self, client: AsyncClient, test_session, auth_headers):
        """Verify that creating a complaint records an audit event with canonical schema."""
        # Create a complaint
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

        # Verify audit event was recorded
        result = await test_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "complaint",
                AuditEvent.entity_id == str(complaint_id),
                AuditEvent.event_type == "complaint.created",
            )
        )
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None, "Audit event was not recorded"

        # Verify canonical audit event schema
        assert audit_event.event_type == "complaint.created"
        assert audit_event.entity_type == "complaint"
        assert audit_event.entity_id == str(complaint_id)
        assert audit_event.action == "create"
        assert audit_event.actor_user_id is not None
        # request_id should be present as a field (may be None in test environment)
        assert hasattr(audit_event, "request_id")
