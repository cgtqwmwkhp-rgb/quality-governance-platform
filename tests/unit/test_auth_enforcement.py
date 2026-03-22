"""Auth enforcement regression tests.

These tests verify that every critical API endpoint correctly rejects
unauthenticated and unauthorized requests. This prevents regressions
where auth guards are accidentally removed or commented out.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.main import app

    return TestClient(app)


TENANT_WRITE_ENDPOINTS = [
    ("POST", "/api/v1/tenants/"),
    ("GET", "/api/v1/tenants/"),
]

INCIDENT_ENDPOINTS = [
    ("GET", "/api/v1/incidents/"),
    ("POST", "/api/v1/incidents/"),
]

COMPLAINT_ENDPOINTS = [
    ("GET", "/api/v1/complaints/"),
    ("POST", "/api/v1/complaints/"),
]

RISK_ENDPOINTS = [
    ("GET", "/api/v1/risks/"),
    ("POST", "/api/v1/risks/"),
]

AUDIT_ENDPOINTS = [
    ("GET", "/api/v1/audits/templates"),
    ("POST", "/api/v1/audits/templates"),
    ("GET", "/api/v1/audits/runs"),
]

NEAR_MISS_ENDPOINTS = [
    ("GET", "/api/v1/near-misses/"),
    ("POST", "/api/v1/near-misses/"),
]

PLANET_MARK_ENDPOINTS = [
    ("GET", "/api/v1/planet-mark/years"),
    ("POST", "/api/v1/planet-mark/years"),
    ("GET", "/api/v1/planet-mark/dashboard"),
    ("GET", "/api/v1/planet-mark/iso14001-mapping"),
]

UVDB_ENDPOINTS = [
    ("GET", "/api/v1/uvdb/protocol"),
    ("GET", "/api/v1/uvdb/sections"),
    ("GET", "/api/v1/uvdb/audits"),
    ("POST", "/api/v1/uvdb/audits"),
    ("GET", "/api/v1/uvdb/dashboard"),
    ("GET", "/api/v1/uvdb/iso-mapping"),
]

WORKFORCE_ENDPOINTS = [
    ("GET", "/api/v1/assessments/"),
    ("POST", "/api/v1/assessments/"),
    ("GET", "/api/v1/inductions/"),
    ("POST", "/api/v1/inductions/"),
    ("GET", "/api/v1/engineers/"),
    ("POST", "/api/v1/engineers/"),
]

ALL_PROTECTED = (
    TENANT_WRITE_ENDPOINTS
    + INCIDENT_ENDPOINTS
    + COMPLAINT_ENDPOINTS
    + RISK_ENDPOINTS
    + AUDIT_ENDPOINTS
    + NEAR_MISS_ENDPOINTS
    + PLANET_MARK_ENDPOINTS
    + UVDB_ENDPOINTS
    + WORKFORCE_ENDPOINTS
)


class TestNoAuthReturns401:
    """Every protected endpoint MUST return 401 without a token."""

    @pytest.mark.parametrize("method,path", ALL_PROTECTED)
    def test_unauthenticated_request_rejected(self, client, method, path):
        response = client.request(method, path)
        assert response.status_code in (401, 403), (
            f"SECURITY REGRESSION: {method} {path} returned {response.status_code} "
            f"without auth token — expected 401 or 403"
        )


class TestBadTokenReturns401:
    """Every protected endpoint MUST reject an invalid JWT."""

    @pytest.mark.parametrize("method,path", ALL_PROTECTED)
    def test_invalid_jwt_rejected(self, client, method, path):
        response = client.request(
            method,
            path,
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.e30.ZRrHA1JJJW8opB1Qfp7QDlaSGR49"},
        )
        assert response.status_code in (401, 403), (
            f"SECURITY REGRESSION: {method} {path} accepted forged JWT " f"(returned {response.status_code})"
        )


class TestExpiredTokenReturns401:
    """Endpoints must reject expired tokens."""

    def test_expired_token_rejected(self, client):
        from datetime import datetime, timedelta, timezone

        import jwt

        expired_payload = {
            "sub": "99999",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "type": "access",
        }
        try:
            from src.core.config import settings

            token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm="HS256")
        except Exception:
            pytest.skip("Cannot create test JWT — settings not available")
            return

        response = client.get(
            "/api/v1/incidents/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (401, 403), f"Expired token accepted (status {response.status_code})"
