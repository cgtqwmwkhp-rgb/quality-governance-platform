"""
Integration tests for reference_number permission guard.

These tests verify that explicit reference_number setting is restricted
to authorized users only (Stage 3.4 Phase 1).
"""

import uuid

import pytest
from httpx import AsyncClient

from src.domain.models.user import Role


class TestReferenceNumberGuard:
    """Test that explicit reference_number requires permission."""

    @pytest.mark.asyncio
    async def test_unauthorized_explicit_reference_number_returns_403(
        self,
        client: AsyncClient,
        test_user,
        test_session,
        auth_headers,
    ):
        """
        Test that unauthorized user cannot set explicit reference_number.

        Expected: 403 Forbidden with canonical error envelope + non-empty request_id
        """
        # test_user does NOT have the permission (no roles assigned)
        # Attempt to create policy with explicit reference_number
        response = await client.post(
            "/api/v1/policies",
            json={
                "title": "Test Policy with Explicit Reference",
                "description": "This should be rejected",
                "document_type": "policy",
                "status": "draft",
                "reference_number": f"POL-GUARD-{uuid.uuid4().hex[:8]}",
            },
            headers=auth_headers,
        )

        # W5 policy write freeze wins before reference-number RBAC
        assert response.status_code == 410
        assert "frozen" in response.text.lower()

    @pytest.mark.asyncio
    async def test_authorized_explicit_reference_number_succeeds(
        self,
        client: AsyncClient,
        test_user,
        test_session,
        auth_headers,
    ):
        """
        Test that authorized user CAN set explicit reference_number.

        Expected: 201 Created with policy containing the explicit reference_number
        """
        # Grant permission to test_user by creating a role
        from sqlalchemy import insert

        from src.domain.models.user import user_roles

        role = Role(
            name=f"policy_admin_{uuid.uuid4().hex[:8]}",
            description="Can set explicit reference numbers",
            permissions='["policy:set_reference_number", "policy:create"]',
        )
        test_session.add(role)
        await test_session.flush()

        # Assign role to user using the association table
        await test_session.execute(insert(user_roles).values(user_id=test_user.id, role_id=role.id))
        await test_session.commit()

        # Create policy with explicit reference_number
        response = await client.post(
            "/api/v1/policies",
            json={
                "title": "Test Policy with Explicit Reference",
                "description": "This should succeed",
                "document_type": "policy",
                "status": "draft",
                "reference_number": f"POL-AUTH-{uuid.uuid4().hex[:8]}",
            },
            headers=auth_headers,
        )

        # W5 policy write freeze wins even for authorized callers
        assert response.status_code == 410
        assert "frozen" in response.text.lower()

    @pytest.mark.asyncio
    async def test_auto_generated_reference_number_no_permission_required(
        self,
        client: AsyncClient,
        test_user,
        test_session,
        auth_headers,
    ):
        """
        Test that auto-generated reference_number does NOT require permission.

        Expected: 201 Created with auto-generated reference_number
        """
        # test_user does NOT have the permission (no roles assigned)
        # Create policy WITHOUT explicit reference_number
        response = await client.post(
            "/api/v1/policies",
            json={
                "title": "Test Policy with Auto Reference",
                "description": "This should succeed without permission",
                "document_type": "policy",
                "status": "draft",
                # NO reference_number provided
            },
            headers=auth_headers,
        )

        # W5 policy write freeze wins before auto reference generation
        assert response.status_code == 410
        assert "frozen" in response.text.lower()
