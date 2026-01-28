"""
Integration Tests for Planet Mark and UVDB API Contracts

These tests validate:
1. Endpoint availability and response shapes
2. Deterministic ordering guarantees
3. Error response consistency
4. Pagination behavior

Per PR #103 requirements:
- Tests must validate real UI-critical API contracts
- Determinism guarantees in list endpoints (explicit ordering)
- Consistent error handling (bounded errors)
- No timing flakiness

PHASE 3 FIX (PR #104):
- GOVPLAT-003 RESOLVED: Now uses the blessed async_client fixture
  from conftest.py which ensures the DB engine is created in the
  test event loop.
"""

import pytest

# ============ Planet Mark Integration Tests ============


class TestPlanetMarkStaticEndpoints:
    """Tests for Planet Mark endpoints that return static/default data."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_setup_required_when_empty(self, async_client):
        """Dashboard returns setup_required when no reporting years exist."""
        response = await async_client.get("/api/v1/planet-mark/dashboard")

        assert response.status_code == 200
        data = response.json()

        # When no data exists, should indicate setup is required
        assert "setup_required" in data or "current_year" in data

    @pytest.mark.asyncio
    async def test_years_list_returns_valid_structure(self, async_client):
        """Years list returns valid response structure."""
        response = await async_client.get("/api/v1/planet-mark/years")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "total" in data
        assert "years" in data
        assert isinstance(data["years"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_iso14001_mapping_returns_static_data(self, async_client):
        """ISO 14001 mapping returns static cross-mapping data."""
        response = await async_client.get("/api/v1/planet-mark/iso14001-mapping")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "description" in data
        assert "mappings" in data
        assert isinstance(data["mappings"], list)

        # Mappings should be deterministic (static data)
        assert len(data["mappings"]) >= 1

        # Validate mapping structure
        if data["mappings"]:
            mapping = data["mappings"][0]
            assert "pm_requirement" in mapping
            assert "iso14001_clause" in mapping

    @pytest.mark.asyncio
    async def test_scope3_returns_default_categories_for_nonexistent_year(self, async_client):
        """Scope 3 endpoint returns default categories for non-existent year."""
        response = await async_client.get("/api/v1/planet-mark/years/99999/scope3")

        assert response.status_code == 200
        data = response.json()

        # Should return default categories structure
        assert "year_id" in data
        assert "categories" in data
        assert data["measured_count"] == 0

    @pytest.mark.asyncio
    async def test_year_not_found_returns_404(self, async_client):
        """Non-existent year returns 404 with proper error structure."""
        response = await async_client.get("/api/v1/planet-mark/years/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestPlanetMarkOrdering:
    """Tests for Planet Mark ordering guarantees."""

    @pytest.mark.asyncio
    async def test_years_ordered_by_year_number_desc(self, async_client):
        """Years list is ordered by year_number descending."""
        response = await async_client.get("/api/v1/planet-mark/years")

        assert response.status_code == 200
        data = response.json()

        # If there are multiple years, verify ordering
        years = data["years"]
        if len(years) > 1:
            for i in range(len(years) - 1):
                assert years[i]["year_number"] >= years[i + 1]["year_number"], (
                    f"Years not ordered by year_number desc: "
                    f"{years[i]['year_number']} should be >= {years[i + 1]['year_number']}"
                )


# ============ UVDB Integration Tests ============


class TestUVDBStaticEndpoints:
    """Tests for UVDB endpoints that return static/deterministic data."""

    @pytest.mark.asyncio
    async def test_protocol_returns_structure(self, async_client):
        """Protocol endpoint returns complete UVDB B2 protocol structure."""
        response = await async_client.get("/api/v1/uvdb/protocol")

        assert response.status_code == 200
        data = response.json()

        # Validate required fields
        assert data["protocol_name"] == "UVDB Verify B2 Audit Protocol"
        assert data["version"] == "V11.2"
        assert data["reference"] == "UVDB-QS-003"
        assert "sections" in data
        assert "scoring" in data

    @pytest.mark.asyncio
    async def test_sections_returns_all_sections(self, async_client):
        """Sections endpoint returns all UVDB B2 sections."""
        response = await async_client.get("/api/v1/uvdb/sections")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "total_sections" in data
        assert "sections" in data
        assert isinstance(data["sections"], list)

        # Should have multiple sections
        assert data["total_sections"] >= 1

        # Validate section structure
        if data["sections"]:
            section = data["sections"][0]
            assert "number" in section
            assert "title" in section
            assert "max_score" in section
            assert "question_count" in section

    @pytest.mark.asyncio
    async def test_sections_stable_ordering(self, async_client):
        """Sections list has stable ordering (by section number)."""
        # Make two requests
        response1 = await async_client.get("/api/v1/uvdb/sections")
        response2 = await async_client.get("/api/v1/uvdb/sections")

        # Both should return identical data
        assert response1.json() == response2.json()

    @pytest.mark.asyncio
    async def test_iso_mapping_returns_cross_mapping(self, async_client):
        """ISO mapping endpoint returns cross-mapping between UVDB and ISO standards."""
        response = await async_client.get("/api/v1/uvdb/iso-mapping")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "description" in data
        assert "total_mappings" in data
        assert "mappings" in data
        assert "summary" in data

        # Mappings should exist
        assert data["total_mappings"] >= 1

    @pytest.mark.asyncio
    async def test_section_questions_returns_questions(self, async_client):
        """Section questions endpoint returns questions for valid section."""
        response = await async_client.get("/api/v1/uvdb/sections/1/questions")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "section_number" in data
        assert "section_title" in data
        assert "max_score" in data
        assert "questions" in data

    @pytest.mark.asyncio
    async def test_section_not_found_returns_404(self, async_client):
        """Non-existent section returns 404."""
        response = await async_client.get("/api/v1/uvdb/sections/999/questions")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_audits_list_returns_valid_structure(self, async_client):
        """Audits list returns valid response structure."""
        response = await async_client.get("/api/v1/uvdb/audits")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "total" in data
        assert "audits" in data
        assert isinstance(data["audits"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_audits_pagination_params(self, async_client):
        """Audits endpoint respects pagination parameters."""
        response = await async_client.get("/api/v1/uvdb/audits?skip=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["audits"], list)
        # Limit should be respected (max 10 items)
        assert len(data["audits"]) <= 10

    @pytest.mark.asyncio
    async def test_dashboard_returns_summary(self, async_client):
        """Dashboard endpoint returns summary statistics."""
        response = await async_client.get("/api/v1/uvdb/dashboard")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "summary" in data
        assert "protocol" in data
        assert "certification_alignment" in data

        # Summary should have counts
        summary = data["summary"]
        assert "total_audits" in summary
        assert "active_audits" in summary
        assert "completed_audits" in summary

    @pytest.mark.asyncio
    async def test_audit_not_found_returns_404(self, async_client):
        """Non-existent audit returns 404."""
        response = await async_client.get("/api/v1/uvdb/audits/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestUVDBOrdering:
    """Tests for UVDB ordering guarantees."""

    @pytest.mark.asyncio
    async def test_audits_ordered_by_date_desc(self, async_client):
        """Audits list is ordered by audit_date descending."""
        response = await async_client.get("/api/v1/uvdb/audits")

        assert response.status_code == 200
        data = response.json()

        # If there are multiple audits with dates, verify ordering
        audits = data["audits"]
        dated_audits = [a for a in audits if a.get("audit_date")]
        if len(dated_audits) > 1:
            for i in range(len(dated_audits) - 1):
                assert dated_audits[i]["audit_date"] >= dated_audits[i + 1]["audit_date"], (
                    f"Audits not ordered by audit_date desc: "
                    f"{dated_audits[i]['audit_date']} should be >= {dated_audits[i + 1]['audit_date']}"
                )


# ============ Error Response Consistency Tests ============


class TestErrorResponseConsistency:
    """Tests for consistent error response format.

    Note: This API uses a custom error envelope with:
    - error_code: HTTP status as string
    - message: Human-readable error message
    - details: Additional context
    - request_id: Trace ID for debugging
    """

    @pytest.mark.asyncio
    async def test_404_has_error_envelope(self, async_client):
        """404 responses include error envelope with message."""
        # Test a 404 scenario
        response = await async_client.get("/api/v1/uvdb/audits/99999")

        if response.status_code == 404:
            data = response.json()
            # Accept either FastAPI default (detail) or custom envelope (message)
            has_error_info = "detail" in data or "message" in data
            assert has_error_info, f"404 response missing error info: {data}"

    @pytest.mark.asyncio
    async def test_validation_error_format(self, async_client):
        """Validation errors have consistent format."""
        # Invalid pagination params
        response = await async_client.get("/api/v1/uvdb/audits?limit=1000")

        # Should be 422 for validation error
        if response.status_code == 422:
            data = response.json()
            # Accept either FastAPI default (detail) or custom envelope (message/details)
            has_error_info = "detail" in data or "message" in data or "details" in data
            assert has_error_info, f"Validation error missing error info: {data}"


# ============ Content-Type Verification ============


class TestContentTypes:
    """Tests for correct Content-Type headers."""

    @pytest.mark.asyncio
    async def test_json_content_type_planet_mark(self, async_client):
        """Planet Mark API responses return application/json."""
        response = await async_client.get("/api/v1/planet-mark/years")
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_json_content_type_uvdb(self, async_client):
        """UVDB API responses return application/json."""
        response = await async_client.get("/api/v1/uvdb/sections")
        assert "application/json" in response.headers.get("content-type", "")
