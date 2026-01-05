"""
RBAC Deny-Path Runtime Contract Tests

Tests that protected endpoints return 403 with canonical error envelopes
when accessed by users without the required permissions.
"""

import pytest
from httpx import AsyncClient

from src.domain.models.user import User


@pytest.mark.asyncio
class TestPoliciesRBACDenyPath:
    """Test RBAC deny-path for Policies module."""

    async def test_create_policy_without_permission_returns_403_canonical_envelope(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test that creating a policy without permission returns 403 with canonical error envelope."""
        # Create a policy without the required permission
        data = {
            "title": "Test Policy",
            "description": "Test Description",
            "policy_type": "quality",
            "status": "draft",
            "version": "1.0",
            "effective_date": "2026-01-01",
        }

        response = await client.post(
            "/api/v1/policies",
            json=data,
            headers=auth_headers,
        )

        # Assert 403 Forbidden
        assert response.status_code == 403

        # Assert canonical error envelope
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "403"
        assert "message" in data
        assert "forbidden" in data["message"].lower() or "permission" in data["message"].lower()
        assert "details" in data
        assert "request_id" in data
        assert data["request_id"] is not None
        assert len(data["request_id"]) > 0


@pytest.mark.asyncio
class TestIncidentsRBACDenyPath:
    """Test RBAC deny-path for Incidents module."""

    async def test_create_incident_without_permission_returns_403_canonical_envelope(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test that creating an incident without permission returns 403 with canonical error envelope."""
        from datetime import datetime, timezone

        data = {
            "title": "Test Incident",
            "description": "Test Description",
            "incident_type": "quality",
            "severity": "medium",
            "status": "reported",
            "incident_date": datetime.now(timezone.utc).isoformat(),
            "reported_date": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            "/api/v1/incidents",
            json=data,
            headers=auth_headers,
        )

        # Assert 403 Forbidden
        assert response.status_code == 403

        # Assert canonical error envelope
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "403"
        assert "message" in data
        assert "forbidden" in data["message"].lower() or "permission" in data["message"].lower()
        assert "details" in data
        assert "request_id" in data
        assert data["request_id"] is not None
        assert len(data["request_id"]) > 0


@pytest.mark.asyncio
class TestComplaintsRBACDenyPath:
    """Test RBAC deny-path for Complaints module."""

    async def test_create_complaint_without_permission_returns_403_canonical_envelope(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test that creating a complaint without permission returns 403 with canonical error envelope."""
        from datetime import datetime, timezone

        data = {
            "title": "Test Complaint",
            "description": "Test Description",
            "complaint_type": "service",
            "priority": "medium",
            "received_date": datetime.now(timezone.utc).isoformat(),
            "complainant_name": "John Doe",
            "complainant_email": "john@example.com",
        }

        response = await client.post(
            "/api/v1/complaints/",
            json=data,
            headers=auth_headers,
        )

        # Debug: print response if not 403
        if response.status_code != 403:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")

        # Assert 403 Forbidden
        assert response.status_code == 403

        # Assert canonical error envelope
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "403"
        assert "message" in data
        assert "forbidden" in data["message"].lower() or "permission" in data["message"].lower()
        assert "details" in data
        assert "request_id" in data
        assert data["request_id"] is not None
        assert len(data["request_id"]) > 0


@pytest.mark.asyncio
class TestRTAsRBACDenyPath:
    """Test RBAC deny-path for RTAs module."""

    async def test_create_rta_without_permission_returns_403_canonical_envelope(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
        test_session,
    ):
        """Test that creating an RTA without permission returns 403 with canonical error envelope."""
        from datetime import datetime, timezone

        from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType

        # Create a test incident first
        incident = Incident(
            title="Test Incident for RTA",
            description="Description",
            incident_type=IncidentType.QUALITY,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.REPORTED,
            incident_date=datetime.now(timezone.utc),
            reported_date=datetime.now(timezone.utc),
            reference_number="INC-2026-RBAC-TEST",
            reporter_id=test_user.id,
            created_by_id=test_user.id,
            updated_by_id=test_user.id,
        )
        test_session.add(incident)
        await test_session.commit()
        await test_session.refresh(incident)

        data = {
            "incident_id": incident.id,
            "title": "Test RTA",
            "problem_statement": "Test problem statement",
            "status": "draft",
        }

        response = await client.post(
            "/api/v1/rtas/",
            json=data,
            headers=auth_headers,
        )

        # Assert 403 Forbidden
        assert response.status_code == 403

        # Assert canonical error envelope
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "403"
        assert "message" in data
        assert "forbidden" in data["message"].lower() or "permission" in data["message"].lower()
        assert "details" in data
        assert "request_id" in data
        assert data["request_id"] is not None
        assert len(data["request_id"]) > 0
