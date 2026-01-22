"""
XSS Protection Tests - Defense in Depth Verification

This test suite verifies security headers are present.

Note: Database-dependent XSS tests are in the UAT suite (SUAT-010, SUAT-011).
The security tests job runs without Postgres, so only header tests are here.

Frontend XSS Protection Evidence:
- React's default JSX escaping for all user-supplied content
- No dangerouslySetInnerHTML is used for user input fields
- See: frontend/src/pages/PortalTrack.tsx lines 206-207, 497
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


class TestXSSProtection:
    """XSS protection verification tests (header-only, no DB required)."""

    @pytest.fixture
    async def client(self):
        """Async HTTP client for XSS tests."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_security_headers_present(self, client):
        """
        Verify security headers are present in API responses.

        Note: Full CSP is configured in staticwebapp.config.json for the frontend.
        The API sets basic security headers via SecurityHeadersMiddleware.
        """
        response = await client.get("/health")
        assert response.status_code == 200

        # Check security headers from SecurityHeadersMiddleware
        headers = response.headers

        # X-Content-Type-Options prevents MIME sniffing
        assert headers.get("x-content-type-options") == "nosniff"

        # X-Frame-Options prevents clickjacking
        assert headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_security_headers_on_error_responses(self, client):
        """Verify security headers are present even on error responses."""
        # Request a protected endpoint without auth
        response = await client.get("/api/v1/incidents/")
        assert response.status_code == 401

        # Security headers should still be present
        headers = response.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_content_type_is_json(self, client):
        """Verify API responses have correct content type."""
        response = await client.get("/health")
        assert response.status_code == 200

        # Content-Type should be JSON
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    @pytest.mark.asyncio
    async def test_no_server_version_disclosure(self, client):
        """Verify server doesn't disclose version information."""
        response = await client.get("/health")

        # Check that server header doesn't expose sensitive info
        server_header = response.headers.get("server", "")

        # Should not contain specific version numbers
        assert "nginx" not in server_header.lower() or "/" not in server_header
        assert "apache" not in server_header.lower()

    @pytest.mark.asyncio
    async def test_options_request_handled_safely(self, client):
        """Verify OPTIONS requests are handled without exposing sensitive info."""
        response = await client.options("/api/v1/incidents/")

        # Should not expose sensitive headers in CORS response
        # (This is a basic check - full CORS testing would need more)
        assert response.status_code in [200, 204, 401, 405]
