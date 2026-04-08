"""
Security headers regression tests (D06 WCS closure 2026-04-08).

Verifies that SecurityHeadersMiddleware in src/main.py emits all required
headers on every response. Any regression in header values will cause CI to fail,
preventing a DAST-flagged vulnerability from being re-introduced.

Headers tested (mapped from OWASP Secure Headers Project):
  - X-Content-Type-Options       : prevents MIME sniffing
  - X-Frame-Options              : prevents clickjacking (legacy browsers)
  - X-XSS-Protection             : 0 = disable broken IE XSS filter
  - Strict-Transport-Security    : enforces HTTPS for 1 year + subdomains
  - Referrer-Policy              : strict-origin-when-cross-origin
  - Permissions-Policy           : denies geolocation, mic, camera
  - Cross-Origin-Opener-Policy   : same-origin
  - Content-Security-Policy      : frame-ancestors 'none' minimum
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from src.main import SecurityHeadersMiddleware


@pytest.fixture()
def secured_client() -> TestClient:
    """Minimal FastAPI app with SecurityHeadersMiddleware applied."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def _test_endpoint():
        return PlainTextResponse("ok")

    @app.get("/health")
    async def _health():
        return PlainTextResponse("ok")

    return TestClient(app, raise_server_exceptions=True)


REQUIRED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "x-xss-protection": "0",
    "referrer-policy": "strict-origin-when-cross-origin",
    "cross-origin-opener-policy": "same-origin",
}


class TestSecurityHeadersPresence:
    """All required OWASP security headers must be present on every response."""

    def test_x_content_type_options(self, secured_client: TestClient) -> None:
        response = secured_client.get("/test")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, secured_client: TestClient) -> None:
        response = secured_client.get("/test")
        assert response.headers.get("x-frame-options") == "DENY"

    def test_x_xss_protection_is_zero(self, secured_client: TestClient) -> None:
        """Must be 0 — enabling XSS protection in modern browsers can introduce vulnerabilities."""
        response = secured_client.get("/test")
        assert response.headers.get("x-xss-protection") == "0"

    def test_hsts_present_and_includes_subdomains(self, secured_client: TestClient) -> None:
        hsts = response = secured_client.get("/test").headers.get("strict-transport-security", "")
        assert "max-age=" in hsts, "HSTS must include max-age"
        assert "includeSubDomains" in hsts, "HSTS must include includeSubDomains"

    def test_referrer_policy(self, secured_client: TestClient) -> None:
        response = secured_client.get("/test")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy_restricts_geolocation(self, secured_client: TestClient) -> None:
        pp = secured_client.get("/test").headers.get("permissions-policy", "")
        assert "geolocation=()" in pp

    def test_permissions_policy_restricts_microphone(self, secured_client: TestClient) -> None:
        pp = secured_client.get("/test").headers.get("permissions-policy", "")
        assert "microphone=()" in pp

    def test_permissions_policy_restricts_camera(self, secured_client: TestClient) -> None:
        pp = secured_client.get("/test").headers.get("permissions-policy", "")
        assert "camera=()" in pp

    def test_cross_origin_opener_policy(self, secured_client: TestClient) -> None:
        response = secured_client.get("/test")
        assert response.headers.get("cross-origin-opener-policy") == "same-origin"

    def test_csp_frame_ancestors_none(self, secured_client: TestClient) -> None:
        csp = secured_client.get("/test").headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp, "CSP must include frame-ancestors 'none' to block clickjacking"

    def test_csp_default_src_self(self, secured_client: TestClient) -> None:
        csp = secured_client.get("/test").headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp

    def test_csp_base_uri_self(self, secured_client: TestClient) -> None:
        csp = secured_client.get("/test").headers.get("content-security-policy", "")
        assert "base-uri 'self'" in csp, "CSP must restrict base-uri to prevent base tag injection"


class TestSecurityHeadersOnHealthEndpoint:
    """Health/readiness endpoints have relaxed CORP but retain all other headers."""

    def test_health_endpoint_still_has_xcto(self, secured_client: TestClient) -> None:
        response = secured_client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_health_endpoint_corp_is_cross_origin(self, secured_client: TestClient) -> None:
        """Health endpoint uses cross-origin CORP so Azure SWA health probes can reach it."""
        response = secured_client.get("/health")
        assert response.headers.get("cross-origin-resource-policy") == "cross-origin"

    def test_non_health_endpoint_corp_is_same_origin(self, secured_client: TestClient) -> None:
        response = secured_client.get("/test")
        assert response.headers.get("cross-origin-resource-policy") == "same-origin"


class TestSecurityHeaderRegression:
    """Regression guard: all required headers must be present together."""

    def test_all_required_headers_present(self, secured_client: TestClient) -> None:
        """Single combined check — ensures no header is silently dropped."""
        response = secured_client.get("/test")
        missing = [header for header, expected in REQUIRED_HEADERS.items() if response.headers.get(header) != expected]
        assert not missing, (
            f"Security header regression detected. Missing or wrong values: {missing}. "
            "This check prevents OWASP/DAST findings from being re-introduced."
        )
