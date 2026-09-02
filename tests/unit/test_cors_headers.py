"""
CORS Header Tests

Validates that CORS headers are present on:
1. Successful responses (2xx)
2. Client error responses (4xx)
3. Server error responses (5xx)
4. OPTIONS preflight responses

This ensures cross-origin requests from the production SWA work correctly.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app

# Production SWA origin
PROD_ORIGIN = "https://purple-water-03205fa03.6.azurestaticapps.net"
# Staging SWA origin — the named pre-production environment, on the regional
# hostname Azure actually serves it from.
STAGING_ORIGIN = "https://purple-water-03205fa03-staging.westeurope.6.azurestaticapps.net"
# Invalid origin
INVALID_ORIGIN = "https://evil.com"
# A Static Web App that is not ours. This used to be allowed: the origin regex
# matched any `*.N.azurestaticapps.net`, so anyone could host a SWA and, because
# the middleware sends credentials, make authenticated cross-origin calls.
FOREIGN_SWA_ORIGIN = "https://test-app.1.azurestaticapps.net"


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


class TestCORSPreflight:
    """Test OPTIONS preflight requests."""

    def test_preflight_returns_200(self, client):
        """OPTIONS preflight should return 200."""
        response = client.options(
            "/api/v1/planet-mark/dashboard",
            headers={
                "Origin": PROD_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert response.status_code == 200

    def test_preflight_has_cors_headers(self, client):
        """OPTIONS preflight should include CORS headers."""
        response = client.options(
            "/api/v1/uvdb/sections",
            headers={
                "Origin": PROD_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN
        assert "GET" in response.headers.get("access-control-allow-methods", "")
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_telemetry_post(self, client):
        """OPTIONS preflight for telemetry POST should work."""
        response = client.options(
            "/api/v1/telemetry/events",
            headers={
                "Origin": PROD_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN
        assert "POST" in response.headers.get("access-control-allow-methods", "")

    def test_preflight_batch_telemetry(self, client):
        """OPTIONS preflight for telemetry batch should work."""
        response = client.options(
            "/api/v1/telemetry/events/batch",
            headers={
                "Origin": PROD_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN

    def test_preflight_staging_origin(self, client):
        """OPTIONS preflight should work for staging SWA origins."""
        response = client.options(
            "/api/v1/planet-mark/dashboard",
            headers={
                "Origin": STAGING_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == STAGING_ORIGIN

    def test_preflight_foreign_static_web_app_is_refused(self, client):
        """A Static Web App that is not ours must not be granted CORS.

        `evil.com` was the only hostile origin covered here, which missed the
        cheaper attack: register any Azure Static Web App and inherit access.
        """
        response = client.options(
            "/api/v1/planet-mark/dashboard",
            headers={
                "Origin": FOREIGN_SWA_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") != FOREIGN_SWA_ORIGIN

    def test_preflight_invalid_origin_no_cors(self, client):
        """OPTIONS preflight should not return CORS for invalid origins."""
        response = client.options(
            "/api/v1/planet-mark/dashboard",
            headers={
                "Origin": INVALID_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should still return 200 but without CORS headers
        assert response.headers.get("access-control-allow-origin") != INVALID_ORIGIN


class TestCORSOnSuccessResponses:
    """Test CORS headers on successful (2xx) responses."""

    def test_get_uvdb_sections_has_cors(self, client):
        """GET /uvdb/sections should include CORS headers regardless of auth status."""
        response = client.get(
            "/api/v1/uvdb/sections",
            headers={"Origin": PROD_ORIGIN},
        )
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN

    def test_get_planetmark_dashboard_has_cors(self, client):
        """GET /planet-mark/dashboard should include CORS headers."""
        response = client.get(
            "/api/v1/planet-mark/dashboard",
            headers={"Origin": PROD_ORIGIN},
        )
        # May be 200 or 401 depending on auth, but should have CORS
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN

    def test_post_telemetry_event_has_cors(self, client):
        """POST /telemetry/events should include CORS headers."""
        response = client.post(
            "/api/v1/telemetry/events",
            headers={"Origin": PROD_ORIGIN, "Content-Type": "application/json"},
            json={
                "name": "exp001_form_opened",
                "timestamp": "2026-01-28T12:00:00Z",
                "sessionId": "test_session",
                "dimensions": {
                    "formType": "incident",
                    "flagEnabled": True,
                    "hasDraft": False,
                },
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN

    def test_post_telemetry_batch_has_cors(self, client):
        """POST /telemetry/events/batch should include CORS headers."""
        response = client.post(
            "/api/v1/telemetry/events/batch",
            headers={"Origin": PROD_ORIGIN, "Content-Type": "application/json"},
            json={
                "events": [
                    {
                        "name": "exp001_form_opened",
                        "timestamp": "2026-01-28T12:00:00Z",
                        "sessionId": "test_session",
                        "dimensions": {
                            "formType": "incident",
                            "flagEnabled": True,
                            "hasDraft": False,
                        },
                    }
                ]
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN


class TestCORSOnErrorResponses:
    """Test CORS headers on error (4xx/5xx) responses."""

    def test_404_has_cors_headers(self, client):
        """404 responses should include CORS headers."""
        response = client.get(
            "/api/v1/nonexistent/endpoint",
            headers={"Origin": PROD_ORIGIN},
        )
        assert response.status_code == 404
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN

    def test_422_validation_error_has_cors(self, client):
        """422 validation errors should include CORS headers."""
        response = client.post(
            "/api/v1/telemetry/events",
            headers={"Origin": PROD_ORIGIN, "Content-Type": "application/json"},
            json={"invalid": "payload"},  # Missing required fields
        )
        assert response.status_code == 422
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN

    def test_invalid_event_name_has_cors(self, client):
        """Invalid telemetry event name (422) should include CORS headers."""
        response = client.post(
            "/api/v1/telemetry/events",
            headers={"Origin": PROD_ORIGIN, "Content-Type": "application/json"},
            json={
                "name": "invalid_event_name",
                "timestamp": "2026-01-28T12:00:00Z",
                "sessionId": "test_session",
                "dimensions": {},
            },
        )
        assert response.status_code == 422
        assert response.headers.get("access-control-allow-origin") == PROD_ORIGIN


class TestCORSExposedHeaders:
    """Test that CORS exposes required headers."""

    def test_expose_rate_limit_headers(self, client):
        """CORS should expose rate limit headers."""
        response = client.get(
            "/api/v1/uvdb/sections",
            headers={"Origin": PROD_ORIGIN},
        )
        expose_headers = response.headers.get("access-control-expose-headers", "")
        assert "X-RateLimit-Limit" in expose_headers or "x-ratelimit-limit" in expose_headers.lower()

    def test_expose_request_id_header(self, client):
        """CORS should expose X-Request-Id header."""
        response = client.get(
            "/api/v1/uvdb/sections",
            headers={"Origin": PROD_ORIGIN},
        )
        expose_headers = response.headers.get("access-control-expose-headers", "")
        assert "X-Request-Id" in expose_headers or "x-request-id" in expose_headers.lower()

    def test_expose_etag_header(self, client):
        """Cross-origin answer writes must expose the refreshed run token."""
        response = client.get(
            "/api/v1/uvdb/sections",
            headers={"Origin": PROD_ORIGIN},
        )
        expose_headers = response.headers.get("access-control-expose-headers", "").lower()
        assert "etag" in expose_headers

    def test_expose_export_download_headers(self, client):
        """Export downloads are cross-origin: the browser must read the filename.

        ``anchor.download`` is set from Content-Disposition, so an unexposed
        header means the saved file loses its name — including the PEL register
        tag a captioned export was requested under (REG-SSOT-E1).
        """
        response = client.get(
            "/api/v1/uvdb/sections",
            headers={"Origin": PROD_ORIGIN},
        )
        expose_headers = response.headers.get("access-control-expose-headers", "").lower()
        assert "content-disposition" in expose_headers
        assert "x-export-truncated" in expose_headers
        assert "x-export-register" in expose_headers
