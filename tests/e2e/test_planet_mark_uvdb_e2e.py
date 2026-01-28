"""
E2E Tests for Planet Mark and UVDB API Flows

These tests validate complete user journeys through the API:
1. Planet Mark dashboard and navigation flows
2. UVDB audit protocol exploration
3. Error handling for edge cases
4. Deterministic rendering (stable list order)

Per PR #103 requirements:
- Tests for real UI-critical flows
- Error state verification for forced failures
- Deterministic rendering assertions

QUARANTINED: [GOVPLAT-004]
Reason: Async event loop conflict between httpx.AsyncClient and the app's
SQLAlchemy asyncpg pool. Same issue as integration tests.

Resolution: Create a proper async_client fixture that initializes the app
within the test's event loop.
Owner: platform-team
Expiry: 2026-02-21
See: docs/runbooks/TEST_QUARANTINE_POLICY.md
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app

# Quarantine: async event loop conflict with DB pool
pytestmark = [
    pytest.mark.skip(
        reason="QUARANTINED [GOVPLAT-004]: Async event loop conflict - "
        "DB pool bound to different loop. Owner: platform-team. Expiry: 2026-02-21. "
        "See docs/runbooks/TEST_QUARANTINE_POLICY.md"
    ),
]


# ============ Planet Mark E2E Tests ============


class TestPlanetMarkDashboardFlow:
    """E2E tests for Planet Mark dashboard user journey."""

    @pytest.mark.asyncio
    async def test_dashboard_loads_and_shows_relevant_data(self):
        """User can load dashboard and see either data or setup required."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Step 1: Load dashboard
            response = await ac.get("/api/v1/planet-mark/dashboard")

            assert response.status_code == 200
            data = response.json()

            # Step 2: Verify structure based on data availability
            if "setup_required" in data and data["setup_required"]:
                # No data case - valid response
                assert data["message"] == "No reporting years configured"
            else:
                # Has data case
                assert "current_year" in data
                assert "emissions_breakdown" in data
                assert "data_quality" in data

    @pytest.mark.asyncio
    async def test_years_navigation_flow(self):
        """User can list years and explore year details."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Step 1: List all years
            response = await ac.get("/api/v1/planet-mark/years")
            assert response.status_code == 200
            years_data = response.json()

            # Step 2: If years exist, try to get details
            if years_data["years"]:
                year_id = years_data["years"][0]["id"]
                detail_response = await ac.get(f"/api/v1/planet-mark/years/{year_id}")
                assert detail_response.status_code == 200
                detail_data = detail_response.json()
                assert "emissions" in detail_data
                assert "data_quality" in detail_data

    @pytest.mark.asyncio
    async def test_scope3_exploration_flow(self):
        """User can explore Scope 3 categories for any year."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Get years
            years_response = await ac.get("/api/v1/planet-mark/years")
            years_data = years_response.json()

            if years_data["years"]:
                year_id = years_data["years"][0]["id"]
                scope3_response = await ac.get(f"/api/v1/planet-mark/years/{year_id}/scope3")
                assert scope3_response.status_code == 200
                scope3_data = scope3_response.json()
                assert "categories" in scope3_data
                # Should have 15 GHG Protocol categories
                if scope3_data["categories"]:
                    assert len(scope3_data["categories"]) == 15

    @pytest.mark.asyncio
    async def test_error_handling_for_invalid_year(self):
        """User gets proper error when accessing non-existent year."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/planet-mark/years/99999")

            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()


class TestPlanetMarkDataQualityFlow:
    """E2E tests for Planet Mark data quality assessment."""

    @pytest.mark.asyncio
    async def test_data_quality_assessment_structure(self):
        """Data quality endpoint returns proper scoring structure."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Get years first
            years_response = await ac.get("/api/v1/planet-mark/years")
            years_data = years_response.json()

            if years_data["years"]:
                year_id = years_data["years"][0]["id"]
                response = await ac.get(f"/api/v1/planet-mark/years/{year_id}/data-quality")
                assert response.status_code == 200
                data = response.json()
                assert "overall_score" in data
                assert "scopes" in data
                assert data["max_score"] == 16


# ============ UVDB E2E Tests ============


class TestUVDBProtocolExplorationFlow:
    """E2E tests for UVDB protocol exploration user journey."""

    @pytest.mark.asyncio
    async def test_protocol_overview_to_section_details(self):
        """User can view protocol overview and drill into sections."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Step 1: Get protocol overview
            protocol_response = await ac.get("/api/v1/uvdb/protocol")
            assert protocol_response.status_code == 200
            protocol_data = protocol_response.json()
            assert protocol_data["protocol_name"] == "UVDB Verify B2 Audit Protocol"

            # Step 2: List all sections
            sections_response = await ac.get("/api/v1/uvdb/sections")
            assert sections_response.status_code == 200
            sections_data = sections_response.json()
            assert sections_data["total_sections"] >= 1

            # Step 3: Get questions for first section
            if sections_data["sections"]:
                section_num = sections_data["sections"][0]["number"]
                questions_response = await ac.get(
                    f"/api/v1/uvdb/sections/{section_num}/questions"
                )
                assert questions_response.status_code == 200
                questions_data = questions_response.json()
                assert "questions" in questions_data

    @pytest.mark.asyncio
    async def test_iso_mapping_exploration(self):
        """User can explore ISO cross-mapping for compliance."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/uvdb/iso-mapping")
            assert response.status_code == 200
            data = response.json()

            # Should have mappings to multiple ISO standards
            assert "summary" in data
            assert "iso_9001_aligned" in data["summary"]
            assert "iso_14001_aligned" in data["summary"]
            assert "iso_45001_aligned" in data["summary"]
            assert "iso_27001_aligned" in data["summary"]


class TestUVDBAuditManagementFlow:
    """E2E tests for UVDB audit management user journey."""

    @pytest.mark.asyncio
    async def test_audit_listing_and_filtering(self):
        """User can list and filter audits."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # List all audits
            all_response = await ac.get("/api/v1/uvdb/audits")
            assert all_response.status_code == 200
            all_data = all_response.json()
            assert "audits" in all_data

            # Filter by status (if any audits exist)
            filtered_response = await ac.get("/api/v1/uvdb/audits?status=completed")
            assert filtered_response.status_code == 200

    @pytest.mark.asyncio
    async def test_dashboard_summary_matches_list(self):
        """Dashboard summary counts should be consistent with list endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Get dashboard
            dashboard_response = await ac.get("/api/v1/uvdb/dashboard")
            assert dashboard_response.status_code == 200
            dashboard_data = dashboard_response.json()

            # Get list
            list_response = await ac.get("/api/v1/uvdb/audits")
            assert list_response.status_code == 200
            list_data = list_response.json()

            # Total should match
            assert dashboard_data["summary"]["total_audits"] == list_data["total"]


class TestDeterministicRendering:
    """Tests to ensure deterministic rendering (stable list order)."""

    @pytest.mark.asyncio
    async def test_sections_list_is_deterministic(self):
        """Sections list returns same order on repeated calls."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            responses = []
            for _ in range(3):
                response = await ac.get("/api/v1/uvdb/sections")
                assert response.status_code == 200
                responses.append(response.json())

            # All responses should be identical
            for i in range(1, len(responses)):
                assert responses[0] == responses[i], (
                    f"Response {i} differs from first response - not deterministic"
                )

    @pytest.mark.asyncio
    async def test_audits_list_is_deterministic(self):
        """Audits list returns same order on repeated calls."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            responses = []
            for _ in range(3):
                response = await ac.get("/api/v1/uvdb/audits?limit=10")
                assert response.status_code == 200
                responses.append(response.json())

            # All responses should be identical
            for i in range(1, len(responses)):
                assert responses[0] == responses[i], (
                    f"Response {i} differs from first response - not deterministic"
                )

    @pytest.mark.asyncio
    async def test_years_list_is_deterministic(self):
        """Years list returns same order on repeated calls."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            responses = []
            for _ in range(3):
                response = await ac.get("/api/v1/planet-mark/years")
                assert response.status_code == 200
                responses.append(response.json())

            # All responses should be identical
            for i in range(1, len(responses)):
                assert responses[0] == responses[i], (
                    f"Response {i} differs from first response - not deterministic"
                )


class TestErrorStateBoundedResponses:
    """Tests for bounded error responses (no stack traces, consistent format)."""

    @pytest.mark.asyncio
    async def test_404_does_not_leak_internals(self):
        """404 errors don't leak internal implementation details."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            endpoints = [
                "/api/v1/planet-mark/years/99999",
                "/api/v1/uvdb/audits/99999",
                "/api/v1/uvdb/sections/invalid/questions",
            ]

            for endpoint in endpoints:
                response = await ac.get(endpoint)
                if response.status_code in [404, 422]:
                    text = response.text.lower()
                    # Should not contain stack traces or internal paths
                    assert "traceback" not in text
                    assert "/src/" not in text
                    assert "file" not in text or "not found" in text

    @pytest.mark.asyncio
    async def test_validation_error_is_helpful(self):
        """Validation errors provide helpful information."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Invalid limit (exceeds max)
            response = await ac.get("/api/v1/uvdb/audits?limit=1000")

            if response.status_code == 422:
                data = response.json()
                assert "detail" in data
                # Should indicate what was wrong
