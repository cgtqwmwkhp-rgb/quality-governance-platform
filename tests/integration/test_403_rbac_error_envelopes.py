"""Integration tests for 403 RBAC error envelope consistency."""

from datetime import datetime

import pytest
from httpx import AsyncClient


class Test403RBACErrorEnvelopes:
    """Test that 403 RBAC denials return canonical error envelopes across modules."""

    @pytest.mark.asyncio
    async def test_policies_403_explicit_reference_number(self, client: AsyncClient, test_session, auth_headers):
        """Verify that Policies returns canonical 403 for unauthorized reference_number."""
        # test_user does NOT have the permission (no roles assigned)
        response = await client.post(
            "/api/v1/policies",
            json={
                "title": "Test Policy",
                "description": "Test",
                "document_type": "policy",
                "status": "draft",
                "reference_number": "POL-2026-TEST",
            },
            headers=auth_headers,
        )

        assert response.status_code == 403

        data = response.json()
        # Verify canonical error envelope keys
        assert "code" in data.get("error", {})
        assert "message" in data.get("error", {})
        assert "details" in data.get("error", {})
        assert "request_id" in data.get("error", {})

        assert isinstance(data["error"]["code"], str)
        assert data["error"]["code"] == "PERMISSION_DENIED"

        assert data["error"]["request_id"] is not None
        assert isinstance(data["error"]["request_id"], str)
        assert len(data["error"]["request_id"]) > 0

        assert "policy:set_reference_number" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_incidents_403_explicit_reference_number(self, client: AsyncClient, test_session, auth_headers):
        """Verify that Incidents returns canonical 403 for unauthorized reference_number."""
        response = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Test Incident",
                "description": "Test",
                "incident_type": "other",
                "severity": "medium",
                "status": "reported",
                "incident_date": datetime.now().isoformat(),
                "reference_number": "INC-2026-TEST",
            },
            headers=auth_headers,
        )

        assert response.status_code == 403

        data = response.json()
        assert "code" in data.get("error", {})
        assert "message" in data.get("error", {})
        assert "details" in data.get("error", {})
        assert "request_id" in data.get("error", {})

        assert isinstance(data["error"]["code"], str)
        assert data["error"]["code"] == "PERMISSION_DENIED"

        assert data["error"]["request_id"] is not None
        assert isinstance(data["error"]["request_id"], str)
        assert len(data["error"]["request_id"]) > 0

        assert "incident:set_reference_number" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_complaints_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that Complaints returns canonical 404 for non-existent resources."""
        response = await client.get("/api/v1/complaints/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        assert "code" in data.get("error", {})
        assert "message" in data.get("error", {})
        assert "details" in data.get("error", {})
        assert "request_id" in data.get("error", {})

        assert isinstance(data["error"]["code"], str)
        assert data["error"]["code"] == "ENTITY_NOT_FOUND"

        assert data["error"]["request_id"] is not None
        assert isinstance(data["error"]["request_id"], str)
        assert len(data["error"]["request_id"]) > 0
