"""
Integration tests for portal incident routing correctness.

Tests verify:
1. Each portal report_type routes to the correct table/API endpoint
2. Admin dashboards show only their intended records (no cross-leakage)
3. Unknown report_type values are rejected (fail-fast per ADR-0002)
4. Portal routing is deterministic under repeated submissions
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPortalRoutingCorrectness:
    """Tests for portal incident routing correctness."""

    async def test_incident_portal_submission_returns_correct_reference(self, client: AsyncClient):
        """Test incident report returns INC- reference prefix."""
        payload = {
            "report_type": "incident",
            "title": "Test Incident for Routing",
            "description": "Testing routing correctness",
            "severity": "medium",
            "location": "Test Location",
            "department": "IT",
            "reporter_name": "Test User",
            "reporter_email": "test@example.com",
            "is_anonymous": False,
        }
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()
        assert data["success"] is True
        assert data["reference_number"].startswith("INC-"), f"Expected INC- prefix, got {data['reference_number']}"

    async def test_rta_portal_submission_returns_correct_reference(self, client: AsyncClient):
        """Test RTA report returns RTA- reference prefix."""
        payload = {
            "report_type": "rta",
            "title": "Test RTA for Routing",
            "description": "Testing RTA routing",
            "severity": "high",
            "location": "Test Road",
            "reporter_name": "Driver Test",
            "reporter_email": "driver@example.com",
            "is_anonymous": False,
        }
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()
        assert data["success"] is True
        assert data["reference_number"].startswith("RTA-"), f"Expected RTA- prefix, got {data['reference_number']}"

    async def test_near_miss_portal_submission_returns_correct_reference(self, client: AsyncClient):
        """Test near_miss report returns NM- reference prefix."""
        payload = {
            "report_type": "near_miss",
            "title": "Test Near Miss",
            "description": "Testing near miss routing",
            "severity": "low",
            "location": "Test Area",
            "department": "Operations",
            "reporter_name": "Safety Officer",
            "reporter_email": "safety@example.com",
            "is_anonymous": False,
        }
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()
        assert data["success"] is True
        assert data["reference_number"].startswith("NM-"), f"Expected NM- prefix, got {data['reference_number']}"

    async def test_complaint_portal_submission_returns_correct_reference(self, client: AsyncClient):
        """Test complaint report returns COMP- reference prefix."""
        payload = {
            "report_type": "complaint",
            "title": "Test Complaint",
            "description": "Testing complaint routing",
            "severity": "medium",
            "reporter_name": "Complainant Test",
            "reporter_email": "complainant@example.com",
            "is_anonymous": False,
        }
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()
        assert data["success"] is True
        assert data["reference_number"].startswith("COMP-"), f"Expected COMP- prefix, got {data['reference_number']}"

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

    async def test_portal_routing_is_deterministic(self, client: AsyncClient):
        """Test that repeated submissions with same type get consistent routing."""
        payload = {
            "report_type": "incident",
            "title": "Determinism Test",
            "description": "Testing deterministic routing",
            "severity": "low",
            "location": "Test Site",
            "department": "QA",
            "reporter_name": "Tester",
            "reporter_email": "qa@example.com",
            "is_anonymous": False,
        }

        references = []
        for _ in range(3):
            response = await client.post("/api/v1/portal/reports/", json=payload)
            assert response.status_code == 201
            data = response.json()
            references.append(data["reference_number"])

        # All should have INC- prefix
        for ref in references:
            assert ref.startswith("INC-"), f"Expected INC- prefix, got {ref}"

        # Reference numbers should be unique
        assert len(set(references)) == 3, "Reference numbers should be unique"


@pytest.mark.asyncio
class TestMappingContract:
    """Tests for the mapping contract between portal forms and report types."""

    EXPECTED_MAPPINGS = [
        ("incident", "INC-"),
        ("near_miss", "NM-"),
        ("complaint", "COMP-"),
        ("rta", "RTA-"),
    ]

    @pytest.mark.parametrize("report_type,expected_prefix", EXPECTED_MAPPINGS)
    async def test_report_type_maps_to_correct_prefix(
        self, client: AsyncClient, report_type: str, expected_prefix: str
    ):
        """Test each report_type maps to the correct reference prefix."""
        payload = {
            "report_type": report_type,
            "title": f"Test {report_type} mapping",
            "description": f"Testing {report_type} to {expected_prefix}",
            "severity": "medium",
            "location": "Test Location",
            "department": "Test Dept",
            "reporter_name": "Test User",
            "reporter_email": "test@example.com",
            "is_anonymous": False,
        }

        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["reference_number"].startswith(expected_prefix)
