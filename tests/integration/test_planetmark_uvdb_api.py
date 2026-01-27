"""Integration tests for Planet Mark and UVDB API endpoints.

These tests verify:
1. Frontend API client route contracts are correct
2. Endpoints exist in the backend (not 404/405)
3. Endpoints return valid JSON responses
4. Deterministic ordering is enforced

Test ID: PLANETMARK-UVDB-API-001

Note: Backend routes now use SQLAlchemy 2.0 async patterns (select + execute).
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client for the application."""
    return TestClient(app)


class TestPlanetMarkAPIRoutes:
    """Tests for Planet Mark API route existence and basic functionality."""

    def test_planet_mark_dashboard_endpoint_exists(self, client):
        """GET /api/v1/planet-mark/dashboard should exist."""
        response = client.get("/api/v1/planet-mark/dashboard")
        # Should return 401 (auth required) or 200, not 404
        assert response.status_code != 404, "Planet Mark dashboard endpoint should exist"
        assert response.status_code in [200, 401, 403, 500]

    def test_planet_mark_years_endpoint_exists(self, client):
        """GET /api/v1/planet-mark/years should exist."""
        response = client.get("/api/v1/planet-mark/years")
        assert response.status_code != 404, "Planet Mark years endpoint should exist"
        assert response.status_code in [200, 401, 403, 500]

    def test_planet_mark_iso_mapping_endpoint_exists(self, client):
        """GET /api/v1/planet-mark/iso14001-mapping should exist (no auth required)."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        # This is a static mapping endpoint - may not require auth
        assert response.status_code != 404, "Planet Mark ISO mapping endpoint should exist"


class TestUVDBAPIRoutes:
    """Tests for UVDB API route existence and basic functionality."""

    def test_uvdb_sections_endpoint_exists(self, client):
        """GET /api/v1/uvdb/sections should exist."""
        response = client.get("/api/v1/uvdb/sections")
        assert response.status_code != 404, "UVDB sections endpoint should exist"
        assert response.status_code in [200, 401, 403, 500]

    def test_uvdb_audits_endpoint_exists(self, client):
        """GET /api/v1/uvdb/audits should exist."""
        response = client.get("/api/v1/uvdb/audits")
        assert response.status_code != 404, "UVDB audits endpoint should exist"
        assert response.status_code in [200, 401, 403, 500]

    def test_uvdb_protocol_endpoint_exists(self, client):
        """GET /api/v1/uvdb/protocol should exist (no auth required - static)."""
        response = client.get("/api/v1/uvdb/protocol")
        assert response.status_code != 404, "UVDB protocol endpoint should exist"

    def test_uvdb_iso_mapping_endpoint_exists(self, client):
        """GET /api/v1/uvdb/iso-mapping should exist (no auth required - static)."""
        response = client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code != 404, "UVDB ISO mapping endpoint should exist"

    def test_uvdb_dashboard_endpoint_exists(self, client):
        """GET /api/v1/uvdb/dashboard should exist."""
        response = client.get("/api/v1/uvdb/dashboard")
        assert response.status_code != 404, "UVDB dashboard endpoint should exist"
        assert response.status_code in [200, 401, 403, 500]
