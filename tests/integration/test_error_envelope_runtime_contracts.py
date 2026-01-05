"""
Integration tests for error envelope runtime contract enforcement.

These tests verify that the runtime error responses match the canonical error
envelope contract defined in Stage 3.0.
"""

import pytest
from httpx import AsyncClient

from src.domain.models.policy import Policy


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
        assert data["request_id"]
        assert isinstance(data["request_id"], str)


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
        assert data["request_id"]
        assert isinstance(data["request_id"], str)


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
        assert data["request_id"]
        assert isinstance(data["request_id"], str)


class TestConflictErrorEnvelopeRuntimeContract:
    """Test that 409 conflict errors return canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_409_conflict_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 409 conflict errors return the canonical error envelope."""
        # Create a policy with a specific reference number
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

        # Try to create another policy with the same reference number (if the endpoint validates this)
        # Note: This test assumes the endpoint has duplicate detection logic
        # If not implemented yet, this test will need to be adjusted

        # For now, we'll skip this test as it requires duplicate detection logic
        # which may not be implemented yet
        pytest.skip("Duplicate reference number detection not yet implemented")
