"""
Integration tests for error envelope runtime contract enforcement.

These tests verify that the runtime error responses match the canonical error
envelope contract defined in Stage 3.0.

Supports both flat format (error_code, message, details, request_id at top level)
and nested format ({"error": {"code": ..., "message": ..., "details": ..., "request_id": ...}}).
"""

import uuid

import pytest
from httpx import AsyncClient


def _extract_error(data: dict) -> tuple:
    """Extract error fields from either flat or nested error envelope format."""
    error = data.get("error", data)
    code = error.get("code", error.get("error_code", ""))
    message = error.get("message", "")
    request_id = error.get("request_id", data.get("request_id", ""))
    return code, message, request_id


class TestPoliciesErrorEnvelopeRuntimeContract:
    """Test that Policies module returns canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 404 errors return the canonical error envelope."""
        response = await client.get("/api/v1/policies/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        code, message, request_id = _extract_error(data)
        assert code, "Error code should be present"
        assert message, "Error message should be present"
        assert request_id, "Request ID should be present"
        assert len(request_id) > 0


class TestIncidentsErrorEnvelopeRuntimeContract:
    """Test that Incidents module returns canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 404 errors return the canonical error envelope."""
        response = await client.get("/api/v1/incidents/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        code, message, request_id = _extract_error(data)
        assert code, "Error code should be present"
        assert message, "Error message should be present"
        assert request_id, "Request ID should be present"
        assert len(request_id) > 0


class TestComplaintsErrorEnvelopeRuntimeContract:
    """Test that Complaints module returns canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_404_not_found_canonical_envelope(self, client: AsyncClient, test_session, auth_headers):
        """Verify that 404 errors return the canonical error envelope."""
        response = await client.get("/api/v1/complaints/999999", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        code, message, request_id = _extract_error(data)
        assert code, "Error code should be present"
        assert message, "Error message should be present"
        assert request_id, "Request ID should be present"
        assert len(request_id) > 0


class TestConflictErrorEnvelopeRuntimeContract:
    """Test that 409 conflict errors return canonical error envelopes at runtime."""

    @pytest.mark.asyncio
    async def test_409_conflict_canonical_envelope(self, client: AsyncClient, test_user, test_session, auth_headers):
        """Verify that 409 conflict errors return the canonical error envelope."""
        from sqlalchemy import insert

        from src.domain.models.user import Role, user_roles

        role = Role(
            name="policy_admin_409",
            description="Can set explicit reference numbers",
            permissions='["policy:set_reference_number"]',
        )
        test_session.add(role)
        await test_session.flush()

        await test_session.execute(insert(user_roles).values(user_id=test_user.id, role_id=role.id))
        await test_session.commit()

        policy_data = {
            "title": "Test Policy 409",
            "description": "Test Description",
            "document_type": "policy",
            "status": "draft",
            "reference_number": f"POL-409-{uuid.uuid4().hex[:8]}",
        }
        response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
        assert response.status_code == 201

        response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
        assert response.status_code == 409

        data = response.json()
        code, message, request_id = _extract_error(data)
        assert code, "Error code should be present"
        assert message, "Error message should be present"
        assert request_id, "Request ID should be present"
        assert len(request_id) > 0
