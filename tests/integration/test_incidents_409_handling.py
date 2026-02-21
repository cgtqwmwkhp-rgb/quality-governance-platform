"""Integration tests for Incidents 409 conflict handling."""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import insert

from src.domain.models.user import Role, user_roles


class TestIncidents409Handling:
    """Test that Incidents module returns 409 for duplicate reference numbers."""

    @pytest.mark.asyncio
    async def test_duplicate_explicit_reference_number_returns_409(
        self,
        client: AsyncClient,
        test_user,
        test_session,
        auth_headers,
    ):
        """
        Test that duplicate explicit reference numbers return 409.

        Expected: 409 Conflict with canonical error envelope + non-empty request_id
        """
        # Grant permission to set explicit reference numbers
        role = Role(
            name="incident_admin_409",
            description="Can set explicit reference numbers",
            permissions='["incident:set_reference_number"]',
        )
        test_session.add(role)
        await test_session.flush()

        await test_session.execute(insert(user_roles).values(user_id=test_user.id, role_id=role.id))
        await test_session.commit()

        # Create first incident with explicit reference number
        incident_data = {
            "title": "Test Incident 409",
            "description": "Test Description",
            "incident_type": "other",
            "severity": "medium",
            "status": "reported",
            "incident_date": datetime.now().isoformat(),
            "reference_number": "INC-2026-TEST1",
        }
        response = await client.post("/api/v1/incidents", json=incident_data, headers=auth_headers)
        assert response.status_code == 201

        # Attempt to create another incident with the same reference number
        response = await client.post("/api/v1/incidents", json=incident_data, headers=auth_headers)
        assert response.status_code == 409

        # Assert canonical error envelope
        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert "details" in data
        assert "request_id" in data

        # Assert error_code is string and equals "409"
        assert isinstance(data["error_code"], str)
        assert data["error_code"] == "409"

        # Assert request_id is non-empty
        assert data["request_id"] is not None
        assert isinstance(data["request_id"], str)
        assert len(data["request_id"]) > 0

        # Assert message contains reference number
        assert "INC-2026-TEST1" in data["message"]
