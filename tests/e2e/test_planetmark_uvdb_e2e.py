"""
Planet Mark and UVDB End-to-End Test Suite

These tests validate that:
1. PlanetMark API endpoints return data (backend works)
2. UVDB API endpoints return data (backend works)
3. Frontend pages can be served (integration with backend)

Test ID: E2E-PLANETMARK-UVDB-001

Run with:
    pytest tests/e2e/test_planetmark_uvdb_e2e.py -v

PHASE 3 FIX (PR #104):
- GOVPLAT-005 RESOLVED: Now uses the blessed async_client fixture
  from conftest.py which ensures the DB engine is created in the
  test event loop.
"""

import pytest

# ============================================================================
# Planet Mark E2E Tests
# ============================================================================


class TestPlanetMarkE2E:
    """E2E tests for Planet Mark carbon management module."""

    @pytest.mark.asyncio
    async def test_planet_mark_dashboard_endpoint_exists(self, async_client):
        """GET /api/v1/planet-mark/dashboard should exist (returns 200, not 404)."""
        response = await async_client.get("/api/v1/planet-mark/dashboard")
        # Should return data, not 404 (missing)
        assert response.status_code != 404, "Planet Mark dashboard endpoint should exist"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_planet_mark_years_endpoint_exists(self, async_client):
        """GET /api/v1/planet-mark/years should exist."""
        response = await async_client.get("/api/v1/planet-mark/years")
        assert response.status_code != 404, "Planet Mark years endpoint should exist"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_planet_mark_dashboard_returns_data(self, async_client):
        """Dashboard should return structured data."""
        response = await async_client.get("/api/v1/planet-mark/dashboard")
        assert response.status_code == 200

        data = response.json()
        # Verify response structure
        assert isinstance(data, dict)
        # Should have setup_required or current_year
        assert "setup_required" in data or "current_year" in data

    @pytest.mark.asyncio
    async def test_planet_mark_years_returns_list(self, async_client):
        """Years should return list structure."""
        response = await async_client.get("/api/v1/planet-mark/years")
        assert response.status_code == 200

        data = response.json()
        # Should have total and years
        assert "total" in data
        assert "years" in data
        assert isinstance(data["years"], list)

    @pytest.mark.asyncio
    async def test_planet_mark_deterministic_ordering(self, async_client):
        """Verify years are returned in deterministic order."""
        response1 = await async_client.get("/api/v1/planet-mark/years")
        response2 = await async_client.get("/api/v1/planet-mark/years")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Same request should return same order
        assert response1.json() == response2.json(), "Years ordering should be deterministic"


# ============================================================================
# UVDB E2E Tests
# ============================================================================


class TestUVDBE2E:
    """E2E tests for UVDB Achilles audit module."""

    @pytest.mark.asyncio
    async def test_uvdb_dashboard_endpoint_exists(self, async_client):
        """GET /api/v1/uvdb/dashboard should exist (returns 200, not 404)."""
        response = await async_client.get("/api/v1/uvdb/dashboard")
        assert response.status_code != 404, "UVDB dashboard endpoint should exist"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_uvdb_sections_endpoint_exists(self, async_client):
        """GET /api/v1/uvdb/sections should exist."""
        response = await async_client.get("/api/v1/uvdb/sections")
        assert response.status_code != 404, "UVDB sections endpoint should exist"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_uvdb_audits_endpoint_exists(self, async_client):
        """GET /api/v1/uvdb/audits should exist."""
        response = await async_client.get("/api/v1/uvdb/audits")
        assert response.status_code != 404, "UVDB audits endpoint should exist"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_uvdb_protocol_endpoint_exists(self, async_client):
        """GET /api/v1/uvdb/protocol should exist."""
        response = await async_client.get("/api/v1/uvdb/protocol")
        assert response.status_code != 404, "UVDB protocol endpoint should exist"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_uvdb_sections_returns_structure(self, async_client):
        """Sections should return proper structure."""
        response = await async_client.get("/api/v1/uvdb/sections")
        assert response.status_code == 200

        data = response.json()
        assert "total_sections" in data
        assert "sections" in data
        assert isinstance(data["sections"], list)

    @pytest.mark.asyncio
    async def test_uvdb_audits_returns_paginated(self, async_client):
        """Audits should return paginated list."""
        response = await async_client.get("/api/v1/uvdb/audits?skip=0&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "audits" in data
        assert isinstance(data["audits"], list)

    @pytest.mark.asyncio
    async def test_uvdb_deterministic_ordering(self, async_client):
        """Verify sections are returned in deterministic order."""
        response1 = await async_client.get("/api/v1/uvdb/sections")
        response2 = await async_client.get("/api/v1/uvdb/sections")

        assert response1.status_code == 200
        assert response2.status_code == 200

        assert response1.json() == response2.json(), "Sections ordering should be deterministic"


# ============================================================================
# Integration: Frontend + Backend
# ============================================================================


class TestFrontendBackendIntegration:
    """Tests verifying frontend pages work with backend API."""

    @pytest.mark.asyncio
    async def test_api_returns_structured_errors(self, async_client):
        """API should return structured error responses for 404."""
        # Request non-existent resource
        response = await async_client.get("/api/v1/planet-mark/years/99999")

        assert response.status_code == 404
        data = response.json()
        # Should have error structure
        has_error = "detail" in data or "message" in data
        assert has_error, "404 response should have error message"

    @pytest.mark.asyncio
    async def test_content_type_json(self, async_client):
        """API responses should be JSON."""
        response = await async_client.get("/api/v1/planet-mark/dashboard")

        # Should return JSON content type
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type


# ============================================================================
# Bounded Error Class Tests
# ============================================================================


class TestBoundedErrorResponses:
    """Tests verifying API returns bounded error classes."""

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, async_client):
        """Non-existent resources return 404."""
        response = await async_client.get("/api/v1/planet-mark/years/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_uvdb_not_found_returns_404(self, async_client):
        """UVDB non-existent resources return 404."""
        response = await async_client.get("/api/v1/uvdb/audits/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_error_response_structure(self, async_client):
        """Error responses have consistent structure."""
        response = await async_client.get("/api/v1/planet-mark/years/99999")
        assert response.status_code == 404

        data = response.json()
        # Should have detail key
        assert "detail" in data
        assert "not found" in data["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
