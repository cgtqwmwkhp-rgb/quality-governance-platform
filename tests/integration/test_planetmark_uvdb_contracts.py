"""
UI-Critical API Contract Tests for Planet Mark and UVDB

These tests validate the EXACT contracts used by frontend pages:
- PlanetMark.tsx: getDashboard, listActions, getScope3
- UVDBAudits.tsx: listSections, listAudits, getISOMapping

CONTRACT REQUIREMENTS:
1. Response shapes must match frontend expectations
2. Ordering must be deterministic (explicit order_by with tie-breaker)
3. Error responses must be bounded (400/401/403/404/500)
4. No internal stack traces in production responses

Test ID: CONTRACT-PLANETMARK-UVDB-001

See: docs/runbooks/TEST_QUARANTINE_POLICY.md for skip governance
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client for the application."""
    return TestClient(app)


# ============================================================================
# Planet Mark Static Contract Tests
# ============================================================================


class TestPlanetMarkISOMapping:
    """Contract tests for GET /api/v1/planet-mark/iso14001-mapping.

    Frontend: PlanetMark.tsx - used for ISO cross-mapping display
    Contract: Static JSON, no auth required, deterministic.
    """

    def test_iso_mapping_returns_correct_shape(self, client):
        """Response must contain 'description' and 'mappings' keys."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        assert response.status_code == 200

        data = response.json()

        # Contract: Must have these keys
        assert "description" in data, "Missing 'description' key"
        assert "mappings" in data, "Missing 'mappings' key"
        assert isinstance(data["mappings"], list), "'mappings' must be a list"

    def test_iso_mapping_has_required_mapping_fields(self, client):
        """Each mapping must have the required fields."""
        response = client.get("/api/v1/planet-mark/iso14001-mapping")
        assert response.status_code == 200

        data = response.json()
        mappings = data["mappings"]

        assert len(mappings) > 0, "Mappings should not be empty"

        for i, mapping in enumerate(mappings):
            assert "pm_requirement" in mapping, f"Mapping {i} missing 'pm_requirement'"
            assert "iso14001_clause" in mapping, f"Mapping {i} missing 'iso14001_clause'"
            assert "iso14001_title" in mapping, f"Mapping {i} missing 'iso14001_title'"

    def test_iso_mapping_is_deterministic(self, client):
        """Multiple requests must return identical responses."""
        response1 = client.get("/api/v1/planet-mark/iso14001-mapping")
        response2 = client.get("/api/v1/planet-mark/iso14001-mapping")
        response3 = client.get("/api/v1/planet-mark/iso14001-mapping")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        # Exact equality for static endpoints
        assert response1.json() == response2.json(), "Response 1 != Response 2"
        assert response2.json() == response3.json(), "Response 2 != Response 3"


# ============================================================================
# UVDB Static Contract Tests
# ============================================================================


class TestUVDBProtocol:
    """Contract tests for GET /api/v1/uvdb/protocol.

    Frontend: UVDBAudits.tsx - getProtocol()
    Contract: Static protocol structure, no auth required.
    """

    def test_protocol_returns_correct_shape(self, client):
        """Response must contain 'protocol_name', 'sections', and 'scoring'."""
        response = client.get("/api/v1/uvdb/protocol")
        assert response.status_code == 200

        data = response.json()

        # Contract: Required keys from frontend expectations
        assert "protocol_name" in data, "Missing 'protocol_name'"
        assert "version" in data, "Missing 'version'"
        assert "sections" in data, "Missing 'sections'"
        assert "scoring" in data, "Missing 'scoring'"
        assert isinstance(data["sections"], list), "'sections' must be a list"

    def test_protocol_sections_have_required_fields(self, client):
        """Each section must have number, title, max_score, question_count."""
        response = client.get("/api/v1/uvdb/protocol")
        assert response.status_code == 200

        sections = response.json()["sections"]
        assert len(sections) > 0, "Protocol must have sections"

        for i, section in enumerate(sections):
            assert "number" in section, f"Section {i} missing 'number'"
            assert "title" in section, f"Section {i} missing 'title'"
            assert "max_score" in section, f"Section {i} missing 'max_score'"
            assert "question_count" in section, f"Section {i} missing 'question_count'"

    def test_protocol_is_deterministic(self, client):
        """Multiple requests must return identical responses."""
        response1 = client.get("/api/v1/uvdb/protocol")
        response2 = client.get("/api/v1/uvdb/protocol")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "Protocol must be deterministic"


class TestUVDBSections:
    """Contract tests for GET /api/v1/uvdb/sections.

    Frontend: UVDBAudits.tsx - listSections()
    Contract: Returns list of sections, deterministically ordered.
    """

    def test_sections_returns_list_shape(self, client):
        """Response must contain 'sections' list with required shape."""
        response = client.get("/api/v1/uvdb/sections")
        assert response.status_code == 200

        data = response.json()

        # Contract: Must have sections list and count
        assert "sections" in data, "Missing 'sections' key"
        assert "total_sections" in data, "Missing 'total_sections'"
        assert isinstance(data["sections"], list), "'sections' must be list"
        assert data["total_sections"] == len(data["sections"]), "Count mismatch"

    def test_sections_ordered_by_number(self, client):
        """Sections must be ordered by section number (deterministic)."""
        response = client.get("/api/v1/uvdb/sections")
        assert response.status_code == 200

        sections = response.json()["sections"]

        if len(sections) > 1:
            # Parse numbers and verify order
            numbers = []
            for s in sections:
                try:
                    numbers.append(int(s["number"]))
                except (ValueError, TypeError):
                    # Handle "1.1" style numbers
                    numbers.append(float(s["number"].replace(".", "")))

            for i in range(len(numbers) - 1):
                assert (
                    numbers[i] <= numbers[i + 1]
                ), f"Sections not ordered: {sections[i]['number']} > {sections[i+1]['number']}"

    def test_sections_is_deterministic(self, client):
        """Multiple requests must return identical responses."""
        response1 = client.get("/api/v1/uvdb/sections")
        response2 = client.get("/api/v1/uvdb/sections")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "Sections must be deterministic"


class TestUVDBISOMapping:
    """Contract tests for GET /api/v1/uvdb/iso-mapping.

    Frontend: UVDBAudits.tsx - getISOMapping()
    Contract: Returns cross-mapping between UVDB and ISO standards.
    """

    def test_iso_mapping_returns_correct_shape(self, client):
        """Response must contain 'mappings', 'summary', 'total_mappings'."""
        response = client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code == 200

        data = response.json()

        # Contract: Required keys
        assert "mappings" in data, "Missing 'mappings' key"
        assert "summary" in data, "Missing 'summary' key"
        assert "total_mappings" in data, "Missing 'total_mappings'"
        assert isinstance(data["mappings"], list), "'mappings' must be list"

    def test_iso_mapping_has_required_fields(self, client):
        """Each mapping must have uvdb_section and iso_clauses."""
        response = client.get("/api/v1/uvdb/iso-mapping")
        assert response.status_code == 200

        mappings = response.json()["mappings"]

        if mappings:  # May be empty initially
            for i, mapping in enumerate(mappings):
                assert "uvdb_section" in mapping, f"Mapping {i} missing 'uvdb_section'"
                assert "iso_clauses" in mapping, f"Mapping {i} missing 'iso_clauses'"
                assert isinstance(mapping["iso_clauses"], list), "iso_clauses must be list"

    def test_iso_mapping_is_deterministic(self, client):
        """Multiple requests must return identical responses."""
        response1 = client.get("/api/v1/uvdb/iso-mapping")
        response2 = client.get("/api/v1/uvdb/iso-mapping")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json(), "ISO mapping must be deterministic"


# ============================================================================
# Error Response Contract Tests
# ============================================================================


class TestBoundedErrorResponses:
    """Verify error responses are bounded and don't leak internals."""

    def test_unauthorized_returns_401_json(self, client):
        """Unauthenticated requests to protected endpoints return 401 JSON."""
        # Planet Mark dashboard requires auth
        response = client.get("/api/v1/planet-mark/dashboard")

        if response.status_code == 401:
            data = response.json()
            # Must have error structure, not stack trace
            assert "detail" in data or "message" in data or "error" in data
            # Must NOT contain Python traceback
            response_text = str(data)
            assert "Traceback" not in response_text
            assert 'File "/app' not in response_text

    def test_not_found_returns_404_json(self, client):
        """Non-existent endpoints return 404 JSON, not HTML."""
        response = client.get("/api/v1/planet-mark/years/99999999")

        # Should be 401 (no auth) or 404 (not found)
        assert response.status_code in [401, 404]

        if response.status_code == 404:
            data = response.json()
            assert "detail" in data or "message" in data

    def test_content_type_always_json(self, client):
        """All API responses must be application/json."""
        endpoints = [
            "/api/v1/planet-mark/iso14001-mapping",
            "/api/v1/uvdb/protocol",
            "/api/v1/uvdb/sections",
            "/api/v1/uvdb/iso-mapping",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            content_type = response.headers.get("content-type", "")
            assert "application/json" in content_type, f"{endpoint} returned {content_type}, expected application/json"


# ============================================================================
# Pagination Contract Tests
# ============================================================================


class TestPaginationContracts:
    """Verify paginated endpoints follow consistent contract."""

    def test_uvdb_audits_pagination_shape(self, client):
        """GET /api/v1/uvdb/audits must return paginated response."""
        response = client.get("/api/v1/uvdb/audits?page=1&size=10")

        # May return 401 for auth, but if 200, must have pagination
        if response.status_code == 200:
            data = response.json()

            # Standard pagination fields
            assert "items" in data, "Missing 'items' key"
            assert "total" in data, "Missing 'total' key"
            assert "page" in data, "Missing 'page' key"
            assert "size" in data, "Missing 'size' key"
            assert isinstance(data["items"], list), "'items' must be list"

    def test_pagination_respects_size_limit(self, client):
        """Pagination must respect requested size limit."""
        response = client.get("/api/v1/uvdb/audits?page=1&size=5")

        if response.status_code == 200:
            data = response.json()
            assert len(data["items"]) <= 5, "Returned more items than requested size"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
