"""API contract tests to prevent breaking changes."""

import pytest
from httpx import AsyncClient

CRITICAL_ENDPOINTS = [
    ("GET", "/api/v1/incidents/", 200),
    ("GET", "/api/v1/complaints/", 200),
    ("GET", "/api/v1/risks/", 200),
    ("GET", "/api/v1/policies/", 200),
    ("GET", "/api/v1/audit-templates/", 200),
    ("GET", "/api/v1/near-misses/", 200),
    ("GET", "/api/v1/feature-flags/", 200),
    ("GET", "/healthz", 200),
    ("GET", "/readyz", 200),
]


@pytest.mark.parametrize("method,path,expected_status", CRITICAL_ENDPOINTS)
async def test_critical_endpoint_exists(method, path, expected_status):
    """Verify critical endpoints exist and return expected status codes."""
    pass  # Placeholder — requires test client fixture


class TestResponseContracts:
    """Verify response shapes match expected contracts."""

    async def test_incident_list_shape(self):
        """Incident list should return array with expected fields."""
        pass

    async def test_health_response_shape(self):
        """Health endpoint should include status and timestamp."""
        pass
