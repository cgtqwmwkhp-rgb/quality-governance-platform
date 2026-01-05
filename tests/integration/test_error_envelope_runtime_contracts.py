"""
Integration tests for error envelope runtime contract enforcement.

These tests verify that the runtime error responses match the canonical error
envelope contract defined in Stage 3.0.
"""

import pytest
from httpx import AsyncClient


class TestPoliciesErrorEnvelopeRuntimeContract:
    """Test that Policies module returns canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 404 errors return the canonical error envelope."""
        response = await client.get("/api/v1/policies/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        # Verify canonical error envelope keys
        assert "error_code" in data
        assert "message" in data
        assert "details" in data
        assert "request_id" in data

        # Verify error_code is a string
        assert isinstance(data["error_code"], str)
        assert data["error_code"] == "404"

        # Verify request_id is present and non-empty
        assert data["request_id"] is not None
        assert isinstance(data["request_id"], str)
        assert len(data["request_id"]) > 0


class TestIncidentsErrorEnvelopeRuntimeContract:
    """Test that Incidents module returns canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 404 errors return the canonical error envelope."""
        response = await client.get("/api/v1/incidents/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        # Verify canonical error envelope keys
        assert "error_code" in data
        assert "message" in data
        assert "details" in data
        assert "request_id" in data

        # Verify error_code is a string
        assert isinstance(data["error_code"], str)
        assert data["error_code"] == "404"

        # Verify request_id is present and non-empty
        assert data["request_id"] is not None
        assert isinstance(data["request_id"], str)
        assert len(data["request_id"]) > 0


class TestComplaintsErrorEnvelopeRuntimeContract:
    """Test that Complaints module returns canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 404 errors return the canonical error envelope."""
        response = await client.get("/api/v1/complaints/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        # Verify canonical error envelope keys
        assert "error_code" in data
        assert "message" in data
        assert "details" in data
        assert "request_id" in data

        # Verify error_code is a string
        assert isinstance(data["error_code"], str)
        assert data["error_code"] == "404"

        # Verify request_id is present and non-empty
        assert data["request_id"] is not None
        assert isinstance(data["request_id"], str)
        assert len(data["request_id"]) > 0


class TestConflictErrorEnvelopeRuntimeContract:
    """Test that 409 conflict errors return canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_409_conflict_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 409 conflict errors return the canonical error envelope."""
        # Create first policy with explicit reference number
        policy_data = {
            "title": "Test Policy 409",
            "description": "Test Description",
            "document_type": "policy",
            "status": "draft",
            "reference_number": "POL-2026-9999",
        }
        response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
        assert response.status_code == 201

        # Attempt to create another policy with the same reference number
        # This should trigger a 409 conflict due to duplicate reference_number
        response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
        assert response.status_code == 409

        data = response.json()
        # Verify canonical error envelope keys
        assert "error_code" in data
        assert "message" in data
        assert "details" in data
        assert "request_id" in data

        # Verify error_code is a string and equals "409"
        assert isinstance(data["error_code"], str)
        assert data["error_code"] == "409"

        # Verify request_id is present and non-empty
        assert data["request_id"] is not None
        assert isinstance(data["request_id"], str)
        assert len(data["request_id"]) > 0
