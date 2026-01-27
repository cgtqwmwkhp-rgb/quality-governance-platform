"""
Planet Mark and UVDB End-to-End Test Suite

These tests validate that:
1. PlanetMark static API endpoints work correctly
2. UVDB static API endpoints work correctly
3. Response structures are correct
4. Deterministic ordering is enforced

Test ID: E2E-PLANETMARK-UVDB-001

Run with:
    pytest tests/e2e/test_planetmark_uvdb_e2e.py -v

Note: Backend routes now use SQLAlchemy 2.0 async patterns (select + execute).
Static endpoints (no database) are tested for full functionality.
Database-dependent endpoints are tested for route existence in integration tests.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def client():
    """Create test client for the application."""
    from fastapi.testclient import TestClient

    from src.main import app

    return TestClient(app)


# ============================================================================
# Planet Mark E2E Tests (Static Endpoints)
# ============================================================================


class TestPlanetMarkE2E:
    """E2E tests for Planet Mark carbon management module."""

    def test_planet_mark_iso_mapping_complete_structure(self, client):
        """GET /api/v1/planet-mark/iso14001-mapping should return complete structure."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        assert response.status_code == 200

        data = response.json()
        assert "description" in data
        assert "mappings" in data
        assert isinstance(data["mappings"], list)

        # Verify mapping structure if any exist
        if data["mappings"]:
            mapping = data["mappings"][0]
            assert "pm_requirement" in mapping
            assert "iso14001_clause" in mapping

    def test_planet_mark_iso_mapping_deterministic(self, client):
        """Verify ISO mapping is returned in deterministic order."""
        response1 = client.get("/api/v1/planet-mark/iso14001-mapping")
        response2 = client.get("/api/v1/planet-mark/iso14001-mapping")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "ISO mapping should be deterministic"


# ============================================================================
# UVDB E2E Tests (Static Endpoints)
# ============================================================================


class TestUVDBE2E:
    """E2E tests for UVDB Achilles audit module."""

    def test_uvdb_protocol_complete_structure(self, client):
        """GET /api/v1/uvdb/protocol should return complete protocol structure."""
        response = client.get("/api/v1/uvdb/protocol")
        assert response.status_code == 200

        data = response.json()
        assert "protocol_name" in data
        assert "version" in data
        assert "sections" in data
        assert "scoring" in data

        # Verify sections is a list
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) > 0, "Should have at least one section"

    def test_uvdb_sections_static_data(self, client):
        """GET /api/v1/uvdb/sections should return sections from static data."""
        response = client.get("/api/v1/uvdb/sections")
        assert response.status_code == 200

        data = response.json()
        assert "total_sections" in data
        assert "sections" in data
        assert isinstance(data["sections"], list)

        # Verify section structure
        if data["sections"]:
            section = data["sections"][0]
            assert "number" in section
            assert "title" in section
            assert "max_score" in section

    def test_uvdb_iso_mapping_complete_structure(self, client):
        """GET /api/v1/uvdb/iso-mapping should return complete ISO mapping."""
        response = client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code == 200

        data = response.json()
        assert "description" in data
        assert "mappings" in data
        assert "summary" in data
        assert "total_mappings" in data

    def test_uvdb_protocol_deterministic(self, client):
        """Verify protocol is returned in deterministic order."""
        response1 = client.get("/api/v1/uvdb/protocol")
        response2 = client.get("/api/v1/uvdb/protocol")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "Protocol should be deterministic"

    def test_uvdb_sections_deterministic(self, client):
        """Verify sections are returned in deterministic order."""
        response1 = client.get("/api/v1/uvdb/sections")
        response2 = client.get("/api/v1/uvdb/sections")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "Sections should be deterministic"


# ============================================================================
# Cross-Module Tests
# ============================================================================


class TestAPIResponses:
    """Tests verifying API response format consistency."""

    def test_content_type_json_planet_mark(self, client):
        """Planet Mark API responses should be JSON."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    def test_content_type_json_uvdb(self, client):
        """UVDB API responses should be JSON."""
        response = client.get("/api/v1/uvdb/protocol")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
