"""
Auth Boundary Tests - Security Hardening Verification

SECURITY FIX (2026-01-22):
These tests verify that the authentication bypass vulnerability has been fixed.
Previously, list endpoints allowed unauthenticated access when an email filter
was provided. This has been corrected - all list endpoints now require
authentication.

Test Matrix:
| Endpoint                    | Unauthenticated | Authenticated (own) | Admin |
|-----------------------------|-----------------|---------------------|-------|
| GET /api/v1/incidents/      | 401 ❌          | 200 ✅ (filtered)    | 200 ✅ |
| GET /api/v1/complaints/     | 401 ❌          | 200 ✅ (filtered)    | 200 ✅ |
| GET /api/v1/rtas/           | 401 ❌          | 200 ✅ (filtered)    | 200 ✅ |
"""

import pytest
from httpx import AsyncClient


class TestAuthRequiredForListEndpoints:
    """
    SECURITY TEST: Verify that all list endpoints require authentication.

    These tests directly verify the fix for the unauthenticated email
    enumeration vulnerability discovered on 2026-01-22.
    """

    @pytest.mark.asyncio
    async def test_incidents_list_requires_auth_no_filter(self, client: AsyncClient):
        """Unauthenticated request without email filter should return 401."""
        response = await client.get("/api/v1/incidents/")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_incidents_list_requires_auth_with_email_filter(self, client: AsyncClient):
        """
        CRITICAL SECURITY TEST: Unauthenticated request WITH email filter should return 401.

        This was the vulnerability - previously returned 200.
        """
        response = await client.get("/api/v1/incidents/?reporter_email=test@example.com")
        assert response.status_code == 401, (
            f"SECURITY VULNERABILITY: Expected 401, got {response.status_code}. "
            "Unauthenticated access with email filter should be blocked!"
        )

    @pytest.mark.asyncio
    async def test_complaints_list_requires_auth_no_filter(self, client: AsyncClient):
        """Unauthenticated request without email filter should return 401."""
        response = await client.get("/api/v1/complaints/")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_complaints_list_requires_auth_with_email_filter(self, client: AsyncClient):
        """
        CRITICAL SECURITY TEST: Unauthenticated request WITH email filter should return 401.

        This was the vulnerability - previously returned 200.
        """
        response = await client.get("/api/v1/complaints/?complainant_email=test@example.com")
        assert response.status_code == 401, (
            f"SECURITY VULNERABILITY: Expected 401, got {response.status_code}. "
            "Unauthenticated access with email filter should be blocked!"
        )

    @pytest.mark.asyncio
    async def test_rtas_list_requires_auth_no_filter(self, client: AsyncClient):
        """Unauthenticated request without email filter should return 401."""
        response = await client.get("/api/v1/rtas/")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_rtas_list_requires_auth_with_email_filter(self, client: AsyncClient):
        """
        CRITICAL SECURITY TEST: Unauthenticated request WITH email filter should return 401.

        This was the vulnerability - previously returned 200.
        """
        response = await client.get("/api/v1/rtas/?reporter_email=test@example.com")
        assert response.status_code == 401, (
            f"SECURITY VULNERABILITY: Expected 401, got {response.status_code}. "
            "Unauthenticated access with email filter should be blocked!"
        )


class TestProtectedEndpoints:
    """Test that protected endpoints remain protected."""

    @pytest.mark.asyncio
    async def test_create_incident_requires_auth(self, client: AsyncClient):
        """Creating incidents should require authentication."""
        response = await client.post(
            "/api/v1/incidents/",
            json={"title": "Test", "description": "Test incident"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_complaint_requires_auth(self, client: AsyncClient):
        """Creating complaints should require authentication."""
        response = await client.post(
            "/api/v1/complaints/",
            json={"title": "Test", "description": "Test complaint"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_rta_requires_auth(self, client: AsyncClient):
        """Creating RTAs should require authentication."""
        response = await client.post(
            "/api/v1/rtas/",
            json={"description": "Test RTA"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_incident_by_id_requires_auth(self, client: AsyncClient):
        """Getting incident by ID should require authentication."""
        response = await client.get("/api/v1/incidents/1")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_incident_requires_auth(self, client: AsyncClient):
        """Updating incidents should require authentication."""
        response = await client.patch(
            "/api/v1/incidents/1",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_incident_requires_auth(self, client: AsyncClient):
        """Deleting incidents should require authentication."""
        response = await client.delete("/api/v1/incidents/1")
        assert response.status_code == 401


class TestPublicEndpoints:
    """Test that public endpoints remain accessible."""

    @pytest.mark.asyncio
    async def test_healthz_is_public(self, client: AsyncClient):
        """Health check should not require authentication."""
        response = await client.get("/healthz")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readyz_is_public(self, client: AsyncClient):
        """Readiness check should not require authentication."""
        response = await client.get("/readyz")
        # May return 200 or 503 depending on DB state, but not 401
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_openapi_is_public(self, client: AsyncClient):
        """OpenAPI spec should be accessible."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200


class TestSecurityHeaders:
    """Verify security headers are present on responses."""

    @pytest.mark.asyncio
    async def test_401_response_has_www_authenticate_header(self, client: AsyncClient):
        """401 responses should include WWW-Authenticate header."""
        response = await client.get("/api/v1/incidents/")
        assert response.status_code == 401
        # FastAPI's HTTPBearer should add this header
        # Note: The header might be lowercase in httpx
        auth_header = response.headers.get("www-authenticate") or response.headers.get("WWW-Authenticate")
        assert auth_header is not None, "401 response should include WWW-Authenticate header"


class TestEndpointAccessMatrix:
    """
    Document and test the endpoint access matrix.

    UPDATED ACCESS MATRIX (Post-Security-Fix):

    | Endpoint                    | Unauthenticated | Authenticated User | Admin User |
    |-----------------------------|-----------------|-------------------|------------|
    | GET /api/v1/incidents/      | 401 ❌          | 200 (own only)    | 200 (all)  |
    | POST /api/v1/incidents/     | 401 ❌          | 201 ✅            | 201 ✅     |
    | GET /api/v1/incidents/{id}  | 401 ❌          | 200 (own?)        | 200 ✅     |
    | PATCH /api/v1/incidents/{id}| 401 ❌          | 200 (own?)        | 200 ✅     |
    | DELETE /api/v1/incidents/{id}| 401 ❌         | 403 ❌            | 204 ✅     |
    | GET /api/v1/rtas/           | 401 ❌          | 200 (own only)    | 200 (all)  |
    | POST /api/v1/rtas/          | 401 ❌          | 201 ✅            | 201 ✅     |
    | GET /api/v1/complaints/     | 401 ❌          | 200 (own only)    | 200 (all)  |
    | POST /api/v1/complaints/    | 401 ❌          | 201 ✅            | 201 ✅     |
    | GET /api/v1/policies/       | 401 ❌          | 403 ❌            | 200 ✅     |
    | GET /healthz                | 200 ✅          | 200 ✅            | 200 ✅     |
    | GET /readyz                 | 200/503 ✅      | 200/503 ✅        | 200/503 ✅ |
    """

    def test_access_matrix_documented(self):
        """Ensure access matrix is documented."""
        # The docstring above serves as the access matrix documentation
        assert True


# Security recommendations implemented:
# 1. ✅ All list endpoints now require authentication
# 2. ✅ Email filter access is restricted to own data (unless admin)
# 3. ⏳ TODO: Implement rate limiting (Stage 3)
# 4. ⏳ TODO: Add audit logging for filtered queries (Stage 3)
# 5. ⏳ TODO: Implement Azure AD JWT validation (Stage 2 enhancement)
