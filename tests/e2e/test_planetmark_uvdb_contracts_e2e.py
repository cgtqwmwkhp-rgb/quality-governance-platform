"""
End-to-End Contract Tests for Planet Mark and UVDB

These tests validate complete request/response cycles for UI-critical endpoints
with a focus on:
1. Response shape matching frontend expectations
2. Deterministic ordering (stable list order)
3. Bounded error states
4. No flakiness from timing or ordering

Test ID: E2E-CONTRACT-001

Run with:
    pytest tests/e2e/test_planetmark_uvdb_contracts_e2e.py -v

See: docs/runbooks/TEST_QUARANTINE_POLICY.md for skip governance
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create test client for the application."""
    return TestClient(app)


# ============================================================================
# Planet Mark E2E Contract Tests
# ============================================================================


class TestPlanetMarkContractsE2E:
    """E2E tests for Planet Mark API contracts.

    These tests verify the EXACT data shape that PlanetMark.tsx expects.
    """

    def test_iso_mapping_complete_response(self, client):
        """
        Frontend Contract: PlanetMark.tsx does NOT call iso14001-mapping directly,
        but this static endpoint provides reference data for ISO alignment.

        Shape: { description: string, mappings: Array<{pm_requirement, iso14001_clause, ...}> }
        """
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        assert response.status_code == 200

        data = response.json()

        # Validate complete response structure
        assert isinstance(data.get("description"), str), "description must be string"
        assert isinstance(data.get("mappings"), list), "mappings must be list"

        # Validate mapping entries
        for mapping in data["mappings"]:
            assert "pm_requirement" in mapping
            assert "iso14001_clause" in mapping
            assert "iso14001_title" in mapping
            assert "mapping_type" in mapping

    def test_iso_mapping_ordering_stability(self, client):
        """
        Determinism: Multiple calls must return mappings in same order.
        This is critical for stable UI rendering.
        """
        responses = [client.get("/api/v1/planet-mark/iso14001-mapping") for _ in range(3)]

        # All must succeed
        for r in responses:
            assert r.status_code == 200

        # All must be identical (including order)
        json_responses = [r.json() for r in responses]
        for i in range(1, len(json_responses)):
            assert json_responses[0] == json_responses[i], f"Response {i} differs from response 0"

    def test_static_iso_endpoint_content_type(self, client):
        """
        All static endpoints must return application/json content type.
        """
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, f"Expected application/json, got {content_type}"


# ============================================================================
# UVDB E2E Contract Tests
# ============================================================================


class TestUVDBContractsE2E:
    """E2E tests for UVDB API contracts.

    These tests verify the EXACT data shape that UVDBAudits.tsx expects.
    """

    def test_protocol_complete_response(self, client):
        """
        Frontend Contract: uvdbApi.getProtocol() - used for protocol display tab

        Shape: {
            protocol_name: string,
            version: string,
            sections: Array<{number, title, max_score, questions: [...]}>,
            scoring: object
        }

        Note: Protocol endpoint returns raw section data with 'questions' array.
        The /sections endpoint provides 'question_count' instead.
        """
        response = client.get("/api/v1/uvdb/protocol")
        assert response.status_code == 200

        data = response.json()

        # Validate required top-level fields
        assert isinstance(data.get("protocol_name"), str), "protocol_name must be string"
        assert isinstance(data.get("version"), str), "version must be string"
        assert isinstance(data.get("sections"), list), "sections must be list"
        assert isinstance(data.get("scoring"), dict), "scoring must be object"

        # Validate section structure
        sections = data["sections"]
        assert len(sections) > 0, "Must have at least one section"

        for section in sections:
            assert "number" in section, "Section missing 'number'"
            assert "title" in section, "Section missing 'title'"
            assert "max_score" in section, "Section missing 'max_score'"
            # Protocol returns 'questions' array, not 'question_count'
            assert (
                "questions" in section or "question_count" in section
            ), "Section must have 'questions' or 'question_count'"

    def test_sections_complete_response(self, client):
        """
        Frontend Contract: uvdbApi.listSections() - used for protocol sections tab

        Shape: {
            total_sections: number,
            sections: Array<{number, title, max_score, question_count}>
        }
        """
        response = client.get("/api/v1/uvdb/sections")
        assert response.status_code == 200

        data = response.json()

        # Validate required fields
        assert "total_sections" in data, "Missing 'total_sections'"
        assert "sections" in data, "Missing 'sections'"
        assert isinstance(data["sections"], list), "sections must be list"

        # Validate consistency
        assert data["total_sections"] == len(
            data["sections"]
        ), "total_sections count doesn't match actual sections length"

    def test_sections_ordered_by_number_ascending(self, client):
        """
        Determinism: Sections must be ordered by section number.

        Frontend: UVDBAudits.tsx sorts client-side as fallback,
        but server MUST provide stable ordering.
        """
        response = client.get("/api/v1/uvdb/sections")
        assert response.status_code == 200

        sections = response.json()["sections"]

        # Extract and compare section numbers
        if len(sections) > 1:
            numbers = [s["number"] for s in sections]
            for i in range(len(numbers) - 1):
                # Handle both numeric "1" and dotted "1.1" formats
                num_a = float(numbers[i]) if "." not in str(numbers[i]) else float(numbers[i])
                num_b = float(numbers[i + 1]) if "." not in str(numbers[i + 1]) else float(numbers[i + 1])
                assert num_a <= num_b, f"Sections not in order: {numbers[i]} should come before {numbers[i+1]}"

    def test_sections_deterministic_over_multiple_calls(self, client):
        """
        Determinism: Multiple calls must return sections in identical order.
        """
        responses = [client.get("/api/v1/uvdb/sections") for _ in range(3)]

        for r in responses:
            assert r.status_code == 200

        json_responses = [r.json() for r in responses]

        # All responses must be identical
        for i in range(1, len(json_responses)):
            assert json_responses[0] == json_responses[i], f"Response {i} differs - ordering is not deterministic"

    def test_iso_mapping_complete_response(self, client):
        """
        Frontend Contract: uvdbApi.getISOMapping()

        Shape: {
            mappings: Array<{uvdb_section, uvdb_question, iso_9001, iso_14001, ...}>,
            summary: object,
            total_mappings: number,
            description: string
        }
        """
        response = client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code == 200

        data = response.json()

        # Validate required fields
        assert "mappings" in data, "Missing 'mappings'"
        assert "summary" in data, "Missing 'summary'"
        assert "total_mappings" in data, "Missing 'total_mappings'"
        assert "description" in data, "Missing 'description'"

        # Validate mappings structure
        for mapping in data["mappings"]:
            assert "uvdb_section" in mapping, "Mapping missing 'uvdb_section'"
            # Endpoint returns iso_XXXX fields directly
            has_iso_fields = any(key.startswith("iso_") for key in mapping.keys())
            assert has_iso_fields, "Mapping must have ISO standard fields"


# ============================================================================
# Response Content-Type Tests
# ============================================================================


class TestResponseContentTypes:
    """Verify all API endpoints return proper content types."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/planet-mark/iso14001-mapping",
            "/api/v1/uvdb/protocol",
            "/api/v1/uvdb/sections",
            "/api/v1/uvdb/iso-mapping",
        ],
    )
    def test_endpoints_return_json_content_type(self, client, endpoint):
        """All endpoints must return application/json."""
        response = client.get(endpoint)
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, f"{endpoint} returned '{content_type}', expected 'application/json'"


# ============================================================================
# Error Boundary Tests
# ============================================================================


class TestErrorBoundaries:
    """Verify error responses are bounded and consistent."""

    def test_404_returns_json_not_html(self, client):
        """Missing resources must return JSON error, not HTML."""
        response = client.get("/api/v1/nonexistent/endpoint")
        assert response.status_code == 404

        # Must be JSON, not HTML
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, "404 must return JSON"

        # Must have error structure
        data = response.json()
        assert "detail" in data, "404 response must have 'detail' field"

    def test_404_error_shape_is_bounded(self, client):
        """404 error responses must have bounded, consistent shape."""
        # Only test static 404 (non-existent route)
        response = client.get("/api/v1/nonexistent/path/here")
        assert response.status_code == 404

        data = response.json()

        # Must have standard error structure
        assert "detail" in data, "404 must have 'detail' field"

        # Must NOT contain Python traceback markers in response
        response_text = response.text
        assert "Traceback (most recent call last)" not in response_text
        assert 'File "/' not in response_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
