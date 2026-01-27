"""
Integration tests for portal incident routing correctness.

Tests verify:
1. Each portal report_type routes to the correct table (via reference prefix)
2. Unknown report_type values are rejected (fail-fast per ADR-0002)

NOTE: Tests are consolidated to avoid event loop issues with async database
connections (see GOVPLAT-ASYNC-001 - mixing sync TestClient with async fixtures
causes "attached to a different loop" errors).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPortalRoutingCorrectness:
    """Tests for portal incident routing correctness."""

    async def test_all_portal_types_route_correctly_and_are_deterministic(self, client: AsyncClient):
        """Test all report types route to correct tables in a single test.

        This test verifies:
        1. Each report_type gets the correct reference prefix
        2. Routing is deterministic (multiple submissions work)
        3. Reference numbers are unique

        Consolidated into single test to avoid event loop issues
        that occur when multiple async tests interact with the
        database connection pool.
        """
        # Test cases: (report_type, expected_prefix, description)
        test_cases = [
            ("incident", "INC-", "incident should get INC- prefix"),
            ("rta", "RTA-", "RTA should get RTA- prefix"),
            ("near_miss", "NM-", "near_miss should get NM- prefix"),
            ("complaint", "COMP-", "complaint should get COMP- prefix"),
        ]

        all_references = []

        for report_type, expected_prefix, description in test_cases:
            payload = {
                "report_type": report_type,
                "title": f"Test {report_type} routing",
                "description": f"Testing {report_type} routes correctly",
                "severity": "medium",
                "location": "Test Location",
                "department": "Test Dept",
                "reporter_name": "Test User",
                "reporter_email": f"test_{report_type}@example.com",
                "is_anonymous": False,
            }

            response = await client.post("/api/v1/portal/reports/", json=payload)
            assert response.status_code == 201, f"{description}: Expected 201, got {response.status_code}"

            data = response.json()
            assert data["success"] is True, f"{description}: success should be True"
            assert data["reference_number"].startswith(
                expected_prefix
            ), f"{description}: Expected {expected_prefix} prefix, got {data['reference_number']}"

            all_references.append(data["reference_number"])

        # Verify all reference numbers are unique (deterministic routing)
        assert len(set(all_references)) == len(all_references), "All reference numbers should be unique"

    async def test_unknown_report_type_rejected(self, client: AsyncClient):
        """Test that unknown report_type is rejected per ADR-0002 fail-fast."""
        payload = {
            "report_type": "unknown_type",
            "title": "Test Unknown Type",
            "description": "This should be rejected",
            "severity": "medium",
            "reporter_name": "Test User",
            "reporter_email": "test@example.com",
            "is_anonymous": False,
        }
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 400, f"Expected 400 for unknown report_type, got {response.status_code}"
