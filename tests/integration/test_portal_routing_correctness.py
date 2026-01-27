"""
Integration tests for portal incident routing correctness.

Tests verify:
1. Each portal report_type routes to the correct table (via reference prefix)
2. Unknown report_type values are rejected (fail-fast per ADR-0002)
3. Portal routing is deterministic under repeated submissions

NOTE: These tests use a single test method to avoid event loop issues
with async database connections (see GOVPLAT-ASYNC-001).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPortalRoutingCorrectness:
    """Tests for portal incident routing correctness."""

    async def test_all_portal_types_route_correctly(self, client: AsyncClient):
        """Test all report types route to correct tables in a single test.

        This avoids event loop issues that occur when multiple async tests
        interact with the database connection pool.
        """
        # Test cases: (report_type, expected_prefix, description)
        test_cases = [
            ("incident", "INC-", "incident should get INC- prefix"),
            ("rta", "RTA-", "RTA should get RTA- prefix"),
            ("near_miss", "NM-", "near_miss should get NM- prefix"),
            ("complaint", "COMP-", "complaint should get COMP- prefix"),
        ]

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


@pytest.mark.asyncio
class TestPortalRoutingDeterminism:
    """Tests for deterministic portal routing behavior."""

    async def test_repeated_submissions_are_deterministic(self, client: AsyncClient):
        """Test that repeated submissions with same type get consistent routing."""
        references = []
        for i in range(3):
            payload = {
                "report_type": "incident",
                "title": f"Determinism Test {i}",
                "description": "Testing deterministic routing",
                "severity": "low",
                "location": "Test Site",
                "department": "QA",
                "reporter_name": "Tester",
                "reporter_email": f"qa_{i}@example.com",
                "is_anonymous": False,
            }

            response = await client.post("/api/v1/portal/reports/", json=payload)
            assert response.status_code == 201
            data = response.json()
            references.append(data["reference_number"])

        # All should have INC- prefix
        for ref in references:
            assert ref.startswith("INC-"), f"Expected INC- prefix, got {ref}"

        # Reference numbers should be unique
        assert len(set(references)) == 3, "Reference numbers should be unique"
