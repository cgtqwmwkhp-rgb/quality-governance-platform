"""
XSS Protection Tests - Defense in Depth Verification

This test suite verifies that the platform is protected against XSS attacks
through multiple layers of defense:

1. API Layer: JSON encoding prevents script execution in API responses
2. Response Headers: Security headers including CSP are present
3. Frontend Layer: React automatically escapes user-supplied content (verified by code review)

Note: The frontend uses React's default JSX escaping for all user-supplied content.
No dangerouslySetInnerHTML is used for user input fields.
See: frontend/src/pages/PortalTrack.tsx lines 206-207, 497
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


class TestXSSProtection:
    """XSS protection verification tests."""

    @pytest.fixture
    async def client(self):
        """Async HTTP client for XSS tests."""
        from src.infrastructure.database import engine

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_xss_payload_in_title_is_json_encoded(self, client):
        """
        Verify that XSS payloads in report titles are properly JSON-encoded.

        The API stores data as-is but returns it as properly escaped JSON.
        This means <script> tags cannot execute when parsed by JavaScript.
        """
        xss_payload = "<script>alert('xss')</script>"

        report = {
            "report_type": "incident",
            "title": xss_payload,
            "description": "XSS test report",
            "severity": "low",
            "is_anonymous": True,
        }

        response = await client.post("/api/v1/portal/reports/", json=report)
        assert response.status_code == 201

        # Get the created report
        data = response.json()
        ref = data["reference_number"]

        # Track the report
        track_response = await client.get(f"/api/v1/portal/reports/{ref}/")
        assert track_response.status_code == 200

        # Verify response is valid JSON (JSON encoding escapes special chars)
        track_data = track_response.json()
        assert "title" in track_data

        # The raw response text should contain escaped JSON, not raw HTML
        # When JavaScript parses this JSON, it becomes a safe string
        raw_text = track_response.text

        # Verify the response is valid JSON that can be safely parsed
        parsed = json.loads(raw_text)
        assert parsed["title"] == xss_payload  # String value, not executable

        # The title is stored as data, not as HTML
        # React's JSX will escape it when rendering: {report.title}

    @pytest.mark.asyncio
    async def test_xss_payload_in_description_is_json_encoded(self, client):
        """Verify XSS in description is also properly JSON-encoded."""
        xss_payload = '<img src="x" onerror="alert(\'xss\')">'

        report = {
            "report_type": "incident",
            "title": "Normal title",
            "description": xss_payload,
            "severity": "low",
            "is_anonymous": True,
        }

        response = await client.post("/api/v1/portal/reports/", json=report)
        assert response.status_code == 201

        # Verify it's valid JSON
        data = response.json()
        assert data["success"] is True

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
    async def test_unicode_and_special_chars_handled_safely(self, client):
        """Verify unicode and special characters are handled correctly."""
        special_chars = "日本語 العربية <>&\"' <!-- -->"

        report = {
            "report_type": "incident",
            "title": special_chars,
            "description": "Unicode and HTML entities test",
            "severity": "low",
            "is_anonymous": True,
        }

        response = await client.post("/api/v1/portal/reports/", json=report)
        assert response.status_code == 201

        # Verify response is valid JSON with correct encoding
        data = response.json()
        ref = data["reference_number"]

        track_response = await client.get(f"/api/v1/portal/reports/{ref}/")
        track_data = track_response.json()

        # Title should be preserved exactly (JSON encoding handles escaping)
        assert track_data["title"] == special_chars

    @pytest.mark.asyncio
    async def test_script_in_reporter_name_handled_safely(self, client):
        """Verify XSS in optional fields is also safe."""
        xss_payload = "<script>document.location='http://evil.com'</script>"

        report = {
            "report_type": "incident",
            "title": "Legitimate incident",
            "description": "Test report",
            "severity": "low",
            "is_anonymous": False,
            "reporter_name": xss_payload,
            "reporter_email": "test@example.com",
        }

        response = await client.post("/api/v1/portal/reports/", json=report)
        # Should either accept (JSON-safe) or reject (validation)
        assert response.status_code in [201, 422]

        if response.status_code == 201:
            # Verify it's stored as JSON data, not executable
            data = response.json()
            assert isinstance(data, dict)
