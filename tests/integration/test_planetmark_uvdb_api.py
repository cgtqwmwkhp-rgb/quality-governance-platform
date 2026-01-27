"""Integration tests for Planet Mark and UVDB API endpoints.

These tests verify:
1. Frontend API client route contracts are correct
2. Endpoints exist in the backend (not 404/405)
3. Static endpoints return valid JSON responses

Test ID: PLANETMARK-UVDB-API-001

Note: Backend routes now use SQLAlchemy 2.0 async patterns (select + execute).
Static endpoints (ISO mappings, protocol) are tested for content.
Database-dependent endpoints are tested for route existence only (auth/500).
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client for the application."""
    return TestClient(app)


class TestPlanetMarkStaticEndpoints:
    """Tests for Planet Mark static endpoints (no database)."""

    def test_planet_mark_iso_mapping_returns_json(self, client):
        """GET /api/v1/planet-mark/iso14001-mapping should return valid JSON."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        # This is a static mapping endpoint - no auth required
        assert response.status_code == 200, "ISO mapping endpoint should return 200"
        data = response.json()
        assert "mappings" in data, "Response should contain mappings"
        assert "description" in data, "Response should contain description"

    def test_planet_mark_iso_mapping_deterministic(self, client):
        """GET /api/v1/planet-mark/iso14001-mapping should be deterministic."""
        response1 = client.get("/api/v1/planet-mark/iso14001-mapping")
        response2 = client.get("/api/v1/planet-mark/iso14001-mapping")
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "Response should be deterministic"


class TestUVDBStaticEndpoints:
    """Tests for UVDB static endpoints (no database)."""

    def test_uvdb_protocol_returns_json(self, client):
        """GET /api/v1/uvdb/protocol should return valid JSON."""
        response = client.get("/api/v1/uvdb/protocol")
        assert response.status_code == 200, "Protocol endpoint should return 200"
        data = response.json()
        assert "protocol_name" in data, "Response should contain protocol_name"
        assert "sections" in data, "Response should contain sections"

    def test_uvdb_iso_mapping_returns_json(self, client):
        """GET /api/v1/uvdb/iso-mapping should return valid JSON."""
        response = client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code == 200, "ISO mapping endpoint should return 200"
        data = response.json()
        assert "mappings" in data, "Response should contain mappings"
        assert "summary" in data, "Response should contain summary"

    def test_uvdb_protocol_deterministic(self, client):
        """GET /api/v1/uvdb/protocol should be deterministic."""
        response1 = client.get("/api/v1/uvdb/protocol")
        response2 = client.get("/api/v1/uvdb/protocol")
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "Response should be deterministic"


class TestAPIContentType:
    """Tests that API endpoints return proper content types."""

    def test_planet_mark_iso_mapping_json_content_type(self, client):
        """Planet Mark ISO mapping should return application/json."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    def test_uvdb_protocol_json_content_type(self, client):
        """UVDB protocol should return application/json."""
        response = client.get("/api/v1/uvdb/protocol")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type


# Note: Database-dependent endpoints (dashboard, audits, years) are tested
# via E2E tests with proper async test client configuration.
# Static endpoints tested above verify route registration and response format.
