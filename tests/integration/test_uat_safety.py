"""
Integration tests for UAT Safety Middleware.

Tests the middleware behavior with actual HTTP requests.
"""

import os
from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def read_only_app():
    """Create app with UAT_MODE=READ_ONLY."""
    # Set env before importing app
    os.environ["UAT_MODE"] = "READ_ONLY"
    os.environ["UAT_ADMIN_USERS"] = "uat_admin_user"

    # Clear settings cache and reimport
    from importlib import reload

    import src.core.config as config_module

    config_module.get_settings.cache_clear()
    reload(config_module)

    from src.main import create_application

    app = create_application()
    return app


@pytest.fixture
def read_write_app():
    """Create app with UAT_MODE=READ_WRITE."""
    os.environ["UAT_MODE"] = "READ_WRITE"

    from importlib import reload

    import src.core.config as config_module

    config_module.get_settings.cache_clear()
    reload(config_module)

    from src.main import create_application

    app = create_application()
    return app


class TestReadOnlyModeBlocking:
    """Tests for write blocking in READ_ONLY mode."""

    @pytest.mark.asyncio
    async def test_post_blocked_without_headers(self, read_only_app):
        """POST request is blocked with 409 in READ_ONLY mode."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/incidents",
                json={"title": "Test"},
            )
            assert response.status_code == 409
            data = response.json()
            assert data["error_class"] == "UAT_WRITE_BLOCKED"

    @pytest.mark.asyncio
    async def test_put_blocked_without_headers(self, read_only_app):
        """PUT request is blocked with 409 in READ_ONLY mode."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            response = await client.put(
                "/api/v1/incidents/1",
                json={"title": "Updated"},
            )
            assert response.status_code == 409
            assert response.json()["error_class"] == "UAT_WRITE_BLOCKED"

    @pytest.mark.asyncio
    async def test_delete_blocked_without_headers(self, read_only_app):
        """DELETE request is blocked with 409 in READ_ONLY mode."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/incidents/1")
            assert response.status_code == 409
            assert response.json()["error_class"] == "UAT_WRITE_BLOCKED"

    @pytest.mark.asyncio
    async def test_get_allowed_in_read_only(self, read_only_app):
        """GET requests are allowed in READ_ONLY mode."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            # Health endpoints should return 200
            response = await client.get("/healthz")
            assert response.status_code == 200

            response = await client.get("/api/v1/meta/version")
            assert response.status_code == 200


class TestAlwaysAllowedPaths:
    """Tests for paths that bypass UAT restrictions."""

    @pytest.mark.asyncio
    async def test_health_endpoints_allowed(self, read_only_app):
        """Health endpoints are always allowed."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            response = await client.get("/healthz")
            assert response.status_code == 200

            response = await client.get("/readyz")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_login_allowed(self, read_only_app):
        """Auth login endpoint is always allowed (POST)."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            # Auth endpoints should not be blocked by UAT middleware
            # They may return 422 for missing data, but not 409
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "test@test.com", "password": "test"},
            )
            # Should not be 409 (UAT blocked)
            assert response.status_code != 409


class TestReadWriteMode:
    """Tests for READ_WRITE mode (staging behavior)."""

    @pytest.mark.asyncio
    async def test_post_allowed_in_read_write(self, read_write_app):
        """POST request is allowed in READ_WRITE mode (returns 401/422, not 409)."""
        async with AsyncClient(
            transport=ASGITransport(app=read_write_app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/incidents",
                json={"title": "Test"},
            )
            # Should not be blocked by UAT middleware
            # May return 401 (auth required) or 422 (validation), but not 409
            assert response.status_code != 409


class TestOverrideHeaders:
    """Tests for override header functionality."""

    @pytest.mark.asyncio
    async def test_override_with_invalid_headers_blocked(self, read_only_app):
        """Override with incomplete headers is blocked."""
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            # Only enable header, missing issue and owner
            response = await client.post(
                "/api/v1/incidents",
                json={"title": "Test"},
                headers={"X-UAT-WRITE-ENABLE": "true"},
            )
            assert response.status_code == 409
            assert "validation failed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_override_with_expired_date_blocked(self, read_only_app):
        """Override with expired date is blocked."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/incidents",
                json={"title": "Test"},
                headers={
                    "X-UAT-WRITE-ENABLE": "true",
                    "X-UAT-ISSUE-ID": "GOVPLAT-123",
                    "X-UAT-OWNER": "qa-team",
                    "X-UAT-EXPIRY": yesterday,
                },
            )
            assert response.status_code == 409
            assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_override_non_admin_blocked(self, read_only_app):
        """Override from non-admin user is blocked."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        async with AsyncClient(
            transport=ASGITransport(app=read_only_app),
            base_url="http://test",
        ) as client:
            # Valid headers but no auth = no user ID = not admin
            response = await client.post(
                "/api/v1/incidents",
                json={"title": "Test"},
                headers={
                    "X-UAT-WRITE-ENABLE": "true",
                    "X-UAT-ISSUE-ID": "GOVPLAT-123",
                    "X-UAT-OWNER": "qa-team",
                    "X-UAT-EXPIRY": tomorrow,
                },
            )
            assert response.status_code == 409
            assert "not authorized" in response.json()["detail"].lower()
