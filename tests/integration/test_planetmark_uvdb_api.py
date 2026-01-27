"""Integration tests for Planet Mark and UVDB API endpoints.

These tests verify:
1. Endpoints exist and respond appropriately
2. Auth is enforced
3. Response structure is correct

Test ID: PLANETMARK-UVDB-API-001

Runs against real PostgreSQL in CI (ADR-0001 compliant).
"""

import pytest
from httpx import AsyncClient


class TestPlanetMarkAPIEndpoints:
    """Test Planet Mark API endpoint contracts."""

    @pytest.mark.asyncio
    async def test_planet_mark_dashboard_requires_auth(self, client: AsyncClient):
        """GET /api/v1/planet-mark/dashboard without auth returns 401."""
        response = await client.get("/api/v1/planet-mark/dashboard")
        # Should return 401 (no auth), not 404 (missing endpoint)
        assert response.status_code != 404, "Planet Mark dashboard should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_planet_mark_years_requires_auth(self, client: AsyncClient):
        """GET /api/v1/planet-mark/years without auth returns 401."""
        response = await client.get("/api/v1/planet-mark/years")
        assert response.status_code != 404, "Planet Mark years should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_planet_mark_year_detail_requires_auth(self, client: AsyncClient):
        """GET /api/v1/planet-mark/years/{id} without auth returns 401."""
        response = await client.get("/api/v1/planet-mark/years/1")
        assert response.status_code != 404, "Planet Mark year detail should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_planet_mark_sources_requires_auth(self, client: AsyncClient):
        """GET /api/v1/planet-mark/years/{id}/sources without auth returns 401."""
        response = await client.get("/api/v1/planet-mark/years/1/sources")
        assert response.status_code != 404, "Planet Mark sources should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_planet_mark_actions_requires_auth(self, client: AsyncClient):
        """GET /api/v1/planet-mark/years/{id}/actions without auth returns 401."""
        response = await client.get("/api/v1/planet-mark/years/1/actions")
        assert response.status_code != 404, "Planet Mark actions should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_planet_mark_scope3_requires_auth(self, client: AsyncClient):
        """GET /api/v1/planet-mark/years/{id}/scope3 without auth returns 401."""
        response = await client.get("/api/v1/planet-mark/years/1/scope3")
        assert response.status_code != 404, "Planet Mark scope3 should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_planet_mark_invalid_token_returns_401(self, client: AsyncClient):
        """Invalid token returns 401, not 500."""
        response = await client.get(
            "/api/v1/planet-mark/dashboard",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
        assert response.headers.get("content-type") == "application/json"


class TestUVDBAPIEndpoints:
    """Test UVDB API endpoint contracts."""

    @pytest.mark.asyncio
    async def test_uvdb_dashboard_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/dashboard without auth returns 401."""
        response = await client.get("/api/v1/uvdb/dashboard")
        assert response.status_code != 404, "UVDB dashboard should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_protocol_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/protocol without auth returns 401."""
        response = await client.get("/api/v1/uvdb/protocol")
        assert response.status_code != 404, "UVDB protocol should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_sections_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/sections without auth returns 401."""
        response = await client.get("/api/v1/uvdb/sections")
        assert response.status_code != 404, "UVDB sections should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_section_questions_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/sections/{id}/questions without auth returns 401."""
        response = await client.get("/api/v1/uvdb/sections/1/questions")
        assert response.status_code != 404, "UVDB section questions should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_audits_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/audits without auth returns 401."""
        response = await client.get("/api/v1/uvdb/audits")
        assert response.status_code != 404, "UVDB audits should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_audits_pagination(self, client: AsyncClient):
        """GET /api/v1/uvdb/audits accepts pagination params."""
        response = await client.get("/api/v1/uvdb/audits?page=1&size=10")
        # Should return 401 (no auth), accepting the query params
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_audit_detail_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/audits/{id} without auth returns 401."""
        response = await client.get("/api/v1/uvdb/audits/1")
        assert response.status_code != 404, "UVDB audit detail should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_iso_mapping_requires_auth(self, client: AsyncClient):
        """GET /api/v1/uvdb/iso-mapping without auth returns 401."""
        response = await client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code != 404, "UVDB ISO mapping should exist"
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uvdb_invalid_token_returns_401(self, client: AsyncClient):
        """Invalid token returns 401, not 500."""
        response = await client.get(
            "/api/v1/uvdb/sections",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
        assert response.headers.get("content-type") == "application/json"


class TestAPIResponseStructure:
    """Test that API responses have correct structure."""

    @pytest.mark.asyncio
    async def test_planet_mark_401_has_error_detail(self, client: AsyncClient):
        """401 response should have error detail."""
        response = await client.get("/api/v1/planet-mark/dashboard")
        assert response.status_code == 401
        data = response.json()
        has_error = "detail" in data or "message" in data or "error" in data
        assert has_error, "401 should have error message"

    @pytest.mark.asyncio
    async def test_uvdb_401_has_error_detail(self, client: AsyncClient):
        """401 response should have error detail."""
        response = await client.get("/api/v1/uvdb/sections")
        assert response.status_code == 401
        data = response.json()
        has_error = "detail" in data or "message" in data or "error" in data
        assert has_error, "401 should have error message"
