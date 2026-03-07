"""API contract tests to prevent breaking changes.

Verifies that critical endpoints exist, return expected status codes,
and respond with the documented response shapes. These tests use the
real FastAPI TestClient to catch regressions before deployment.
"""

import pytest
from fastapi.testclient import TestClient

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/incidents/"),
    ("GET", "/api/v1/complaints/"),
    ("GET", "/api/v1/risks/"),
    ("GET", "/api/v1/policies"),
    ("GET", "/api/v1/audits/templates"),
    ("GET", "/api/v1/near-misses/"),
]

PUBLIC_ENDPOINTS = [
    ("GET", "/healthz", 200),
    ("GET", "/readyz", {200, 503}),
]


@pytest.fixture(scope="module")
def test_client():
    from src.main import app

    return TestClient(app)


# ============================================================================
# Public Endpoints
# ============================================================================


class TestPublicEndpoints:
    """Public endpoints must return 200 without auth."""

    @pytest.mark.parametrize("method,path,expected_status", PUBLIC_ENDPOINTS)
    def test_public_endpoint_reachable(self, test_client, method, path, expected_status):
        response = test_client.request(method, path)
        acceptable = expected_status if isinstance(expected_status, set) else {expected_status}
        assert (
            response.status_code in acceptable
        ), f"{method} {path} returned {response.status_code}, expected one of {acceptable}"


# ============================================================================
# Auth Enforcement
# ============================================================================


class TestProtectedEndpointAuth:
    """Protected endpoints must reject unauthenticated requests."""

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_returns_401_without_token(self, test_client, method, path):
        response = test_client.request(method, path)
        assert response.status_code in (
            401,
            403,
        ), f"{method} {path} returned {response.status_code} without auth, expected 401/403"

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_returns_401_with_invalid_token(self, test_client, method, path):
        response = test_client.request(method, path, headers={"Authorization": "Bearer invalid.jwt.token"})
        assert response.status_code in (
            401,
            403,
        ), f"{method} {path} accepted invalid JWT (status {response.status_code})"


# ============================================================================
# Response Shape Contracts
# ============================================================================


class TestResponseContracts:
    """Verify response shapes match expected contracts."""

    def test_health_response_shape(self, test_client):
        response = test_client.get("/healthz")
        data = response.json()
        assert "status" in data, "Health response must include 'status' field"

    def test_readyz_response_shape(self, test_client):
        response = test_client.get("/readyz")
        assert response.status_code in (200, 503)

    def test_openapi_schema_available(self, test_client):
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "info" in schema
        assert len(schema["paths"]) > 0, "OpenAPI schema must contain at least one path"


# ============================================================================
# Incident Contract
# ============================================================================


class TestIncidentContract:
    """Contract tests for the incident CRUD lifecycle."""

    def test_incident_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/incidents/")
        assert response.status_code in (401, 403)

    def test_incident_create_requires_auth(self, test_client):
        response = test_client.post(
            "/api/v1/incidents/",
            json={"title": "Test", "severity": "low", "incident_type": "other"},
        )
        assert response.status_code in (401, 403)

    def test_incident_create_validates_body(self, test_client, auth_headers):
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.post(
            "/api/v1/incidents/",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422, "Empty body should trigger validation error"

    def test_incident_list_returns_paginated_shape(self, test_client, auth_headers):
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/incidents/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data, "List response must include 'items'"
        assert "total" in data, "List response must include 'total'"
        assert "page" in data, "List response must include 'page'"
        assert isinstance(data["items"], list)

    def test_incident_404_for_nonexistent(self, test_client, auth_headers):
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/incidents/999999", headers=auth_headers)
        assert response.status_code == 404


# ============================================================================
# Complaint Contract
# ============================================================================


class TestComplaintContract:
    """Contract tests for the complaint CRUD lifecycle."""

    def test_complaint_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/complaints/")
        assert response.status_code in (401, 403)

    def test_complaint_create_requires_auth(self, test_client):
        response = test_client.post(
            "/api/v1/complaints/",
            json={"title": "Test complaint"},
        )
        assert response.status_code in (401, 403)

    def test_complaint_list_returns_paginated_shape(self, test_client, auth_headers):
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/complaints/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


# ============================================================================
# Risk Contract
# ============================================================================


class TestRiskContract:
    """Contract tests for the risk register."""

    def test_risk_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/risks/")
        assert response.status_code in (401, 403)

    def test_risk_create_requires_auth(self, test_client):
        response = test_client.post(
            "/api/v1/risks/",
            json={"title": "Test risk", "likelihood": 3, "impact": 3},
        )
        assert response.status_code in (401, 403)

    def test_risk_matrix_requires_auth(self, test_client):
        response = test_client.get("/api/v1/risks/matrix")
        assert response.status_code in (401, 403)

    def test_risk_list_returns_paginated_shape(self, test_client, auth_headers):
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/risks/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_risk_statistics_requires_auth(self, test_client):
        response = test_client.get("/api/v1/risks/statistics")
        assert response.status_code in (401, 403)


# ============================================================================
# Audit Contract
# ============================================================================


class TestAuditContract:
    """Contract tests for the audit & inspection system."""

    def test_audit_template_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/audits/templates")
        assert response.status_code in (401, 403)

    def test_audit_run_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/audits/runs")
        assert response.status_code in (401, 403)

    def test_audit_finding_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/audits/findings")
        assert response.status_code in (401, 403)

    def test_audit_template_list_returns_paginated_shape(self, test_client, auth_headers):
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/audits/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_audit_template_create_requires_auth(self, test_client):
        response = test_client.post(
            "/api/v1/audits/templates",
            json={"name": "Test Template", "audit_type": "internal"},
        )
        assert response.status_code in (401, 403)


# ============================================================================
# Near Miss Contract
# ============================================================================


class TestNearMissContract:
    """Contract tests for near-miss reporting."""

    def test_near_miss_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/near-misses/")
        assert response.status_code in (401, 403)

    def test_near_miss_create_requires_auth(self, test_client):
        response = test_client.post(
            "/api/v1/near-misses/",
            json={"title": "Test near miss"},
        )
        assert response.status_code in (401, 403)


# ============================================================================
# Tenant Contract
# ============================================================================


class TestTenantContract:
    """Contract tests for tenant management (superuser-only endpoints)."""

    def test_tenant_list_requires_auth(self, test_client):
        response = test_client.get("/api/v1/tenants/")
        assert response.status_code in (401, 403)

    def test_tenant_create_requires_auth(self, test_client):
        response = test_client.post(
            "/api/v1/tenants/",
            json={"name": "Test Tenant", "slug": "test-tenant"},
        )
        assert response.status_code in (401, 403)


# ============================================================================
# API Versioning
# ============================================================================


class TestCriticalPathVersioning:
    """Ensure all critical paths use versioned /api/v1/ prefix."""

    def test_openapi_paths_are_versioned(self, test_client):
        response = test_client.get("/openapi.json")
        schema = response.json()

        unversioned = [path for path in schema["paths"] if path.startswith("/api/") and not path.startswith("/api/v1/")]
        assert unversioned == [], f"Unversioned API paths found: {unversioned}"

    def test_openapi_has_expected_critical_paths(self, test_client):
        response = test_client.get("/openapi.json")
        schema = response.json()
        paths = set(schema.get("paths", {}).keys())

        required_paths = [
            "/api/v1/incidents/",
            "/api/v1/complaints/",
            "/api/v1/risks/",
        ]

        for required in required_paths:
            assert required in paths, f"Critical path {required} missing from OpenAPI schema"


# ============================================================================
# Response Headers Contract
# ============================================================================


class TestSecurityHeadersContract:
    """Verify security headers are present on responses."""

    def test_health_endpoint_returns_expected_content_type(self, test_client):
        response = test_client.get("/healthz")
        assert "application/json" in response.headers.get("content-type", "")
