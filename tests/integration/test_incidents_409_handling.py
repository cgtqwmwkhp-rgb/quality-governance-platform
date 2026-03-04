"""Integration tests for Incidents 409 conflict handling."""

import uuid
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
        ref_number = f"INC-409-{uuid.uuid4().hex[:8]}"
        incident_data = {
            "title": "Test Incident 409",
            "description": "Test Description",
            "incident_type": "other",
            "severity": "medium",
            "status": "reported",
            "incident_date": datetime.now().isoformat(),
            "reference_number": ref_number,
        }
        response = await client.post("/api/v1/incidents/", json=incident_data, headers=auth_headers)
        assert response.status_code == 201

        # Attempt to create another incident with the same reference number
        response = await client.post("/api/v1/incidents/", json=incident_data, headers=auth_headers)
        assert response.status_code == 409

        # Assert canonical error envelope (supports both flat and nested formats)
        data = response.json()
        error = data.get("error", data)
        error_code = error.get("code", error.get("error_code", ""))
        message = error.get("message", "")
        request_id = error.get("request_id", data.get("request_id", ""))

        assert error_code, "Error code should be present"
        assert message, "Error message should be present"
        assert request_id, "Request ID should be present"
        assert len(request_id) > 0

        # Assert message contains reference number
        assert ref_number in message
