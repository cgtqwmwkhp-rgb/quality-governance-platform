"""
Portal Authentication Tests

Tests for the portal authentication flow including:
- Token exchange endpoint
- My-reports endpoint with proper auth
- Email enumeration prevention
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


class TestPortalAuth:
    """Tests for portal authentication endpoints."""

    @pytest.fixture
    async def client(self):
        """Async HTTP client for portal auth tests."""
        from src.infrastructure.database import engine

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_token_exchange_requires_valid_token(self, client):
        """Token exchange should reject invalid Azure AD tokens."""
        response = await client.post(
            "/api/v1/auth/token-exchange",
            json={"id_token": "invalid-token"},
        )
        # Should reject with 401 (invalid token)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_token_exchange_requires_token(self, client):
        """Token exchange should require id_token field."""
        response = await client.post(
            "/api/v1/auth/token-exchange",
            json={},
        )
        # Should reject with 422 (validation error)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_my_reports_requires_auth(self, client):
        """My-reports endpoint should require authentication."""
        response = await client.get("/api/v1/portal/my-reports/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_my_reports_rejects_invalid_token(self, client):
        """My-reports should reject invalid tokens."""
        response = await client.get(
            "/api/v1/portal/my-reports/",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_portal_reports_still_public(self, client):
        """Portal report submission should still be public."""
        response = await client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "Test incident for auth verification",
                "description": "This is a test incident to verify auth works",
                "severity": "low",
                "is_anonymous": True,
            },
        )
        # Portal submission is public
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_incidents_list_requires_auth(self, client):
        """Incidents list should require authentication."""
        response = await client.get("/api/v1/incidents/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_incidents_list_with_email_filter_requires_auth(self, client):
        """
        Incidents list with email filter should require auth.
        This prevents email enumeration attacks.
        """
        response = await client.get("/api/v1/incidents/?reporter_email=test@example.com")
        assert response.status_code == 401


class TestEmailEnumerationPrevention:
    """Tests to ensure email enumeration is prevented."""

    @pytest.fixture
    async def client(self):
        """Async HTTP client."""
        from src.infrastructure.database import engine

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_cannot_enumerate_incidents_by_email(self, client):
        """Users cannot enumerate incidents by guessing emails."""
        # Without auth, should get 401
        response = await client.get("/api/v1/incidents/?reporter_email=victim@example.com")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cannot_enumerate_complaints_by_email(self, client):
        """Users cannot enumerate complaints by guessing emails."""
        response = await client.get("/api/v1/complaints/?complainant_email=victim@example.com")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cannot_enumerate_rtas_by_email(self, client):
        """Users cannot enumerate RTAs by guessing emails."""
        response = await client.get("/api/v1/rtas/?reporter_email=victim@example.com")
        assert response.status_code == 401
