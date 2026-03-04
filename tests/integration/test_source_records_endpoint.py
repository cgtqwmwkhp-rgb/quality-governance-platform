"""
Tests for GET /api/v1/investigations/source-records endpoint.

Tests for:
- AuthN requirement (401 without token)
- Deterministic ordering (created_at DESC, id ASC)
- Bounded pagination (max 100 per page)
- Investigated records flagged with investigation_id
- Display labels are non-PII (reference_number + title only)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSourceRecordsAuth:
    """AuthN tests for source-records endpoint."""

    async def test_requires_authentication(self, client: AsyncClient):
        """Test endpoint requires authentication."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
        )
        assert response.status_code == 401

    async def test_authenticated_access(self, client: AsyncClient, auth_headers: dict):
        """Test authenticated user can access endpoint."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
            headers=auth_headers,
        )
        assert response.status_code == 200


@pytest.mark.asyncio
class TestSourceRecordsDeterminism:
    """Deterministic ordering and pagination tests."""

    async def test_deterministic_ordering(self, client: AsyncClient, auth_headers: dict):
        """Test results are ordered by created_at DESC, id ASC."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss", "page": 1, "size": 50},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        items = data["items"]
        if len(items) >= 2:
            # Verify ordering: created_at descending
            for i in range(len(items) - 1):
                curr_created = items[i]["created_at"]
                next_created = items[i + 1]["created_at"]
                # If same created_at, id should be ascending
                if curr_created == next_created:
                    assert items[i]["source_id"] <= items[i + 1]["source_id"]
                else:
                    assert curr_created >= next_created

    async def test_pagination_bounded(self, client: AsyncClient, auth_headers: dict):
        """Test pagination is bounded to max 100 items."""
        # Request more than max should be capped
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss", "page": 1, "size": 200},
            headers=auth_headers,
        )
        # Should return 422 validation error for size > 100
        assert response.status_code == 422

    async def test_pagination_response_structure(self, client: AsyncClient, auth_headers: dict):
        """Test pagination response has required fields."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss", "page": 1, "size": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Required pagination fields
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert "source_type" in data

        # Verify values
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert isinstance(data["total"], int)
        assert isinstance(data["total_pages"], int)


@pytest.mark.asyncio
class TestSourceRecordsDisplayLabels:
    """Test display labels are safe (no PII)."""

    async def test_display_label_format(self, client: AsyncClient, auth_headers: dict):
        """Test display labels use safe format: {reference_number} — {status} — {date}."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        for item in data["items"]:
            # Required fields
            assert "source_id" in item
            assert "display_label" in item
            assert "reference_number" in item
            assert "status" in item
            assert "created_at" in item

            display_label = item["display_label"]

            # Display label MUST start with reference number
            assert display_label.startswith(
                item["reference_number"]
            ), f"Label must start with reference: {display_label}"

            # Display label MUST contain em-dash separators (safe format)
            assert " — " in display_label, f"Label must use safe format with em-dash: {display_label}"

            # Display label MUST contain status (uppercase)
            assert item["status"].upper() in display_label, f"Label must contain status: {display_label}"

            # Display label MUST contain date pattern (YYYY-MM-DD)
            import re

            assert re.search(r"\d{4}-\d{2}-\d{2}", display_label), f"Label must contain date pattern: {display_label}"

    async def test_display_label_no_pii(self, client: AsyncClient, auth_headers: dict):
        """Test display labels do not contain PII patterns."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        for item in data["items"]:
            display_label = item["display_label"]

            # NO email patterns
            assert "@" not in display_label, f"Label contains email pattern: {display_label}"

            # NO phone patterns (11+ consecutive digits)
            import re

            assert not re.search(r"\d{11,}", display_label), f"Label contains phone pattern: {display_label}"

            # Label should NOT contain common name patterns (Mr/Ms/Mrs/Dr + word)
            assert not re.search(
                r"\b(Mr|Ms|Mrs|Dr|Miss)\s+\w+", display_label, re.IGNORECASE
            ), f"Label contains name pattern: {display_label}"


@pytest.mark.asyncio
class TestSourceRecordsInvestigationStatus:
    """Test investigated records are properly flagged."""

    async def test_investigated_record_has_investigation_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        near_miss_with_investigation: tuple,
    ):
        """Test records with investigations have investigation_id set."""
        near_miss, investigation = near_miss_with_investigation

        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Find the investigated record
        investigated = next(
            (item for item in data["items"] if item["source_id"] == near_miss.id),
            None,
        )

        if investigated:
            assert investigated["investigation_id"] == investigation.id
            assert investigated["investigation_reference"] == investigation.reference_number

    async def test_uninvestigated_record_has_null_investigation(
        self, client: AsyncClient, auth_headers: dict, near_miss_factory
    ):
        """Test records without investigations have null investigation_id."""
        # Create a near miss without investigation
        near_miss = await near_miss_factory()

        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Find the uninvestigated record
        uninvestigated = next(
            (item for item in data["items"] if item["source_id"] == near_miss.id),
            None,
        )

        if uninvestigated:
            assert uninvestigated["investigation_id"] is None
            assert uninvestigated["investigation_reference"] is None


@pytest.mark.asyncio
class TestSourceRecordsValidation:
    """Input validation tests."""

    async def test_invalid_source_type_returns_400(self, client: AsyncClient, auth_headers: dict):
        """Test invalid source_type returns 400 with error code."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "invalid_type"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "INVALID_SOURCE_TYPE"

    async def test_missing_source_type_returns_422(self, client: AsyncClient, auth_headers: dict):
        """Test missing source_type returns 422."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "source_type",
        ["near_miss", "road_traffic_collision", "complaint", "reporting_incident"],
    )
    async def test_all_source_types_work(self, client: AsyncClient, auth_headers: dict, source_type: str):
        """Test all valid source types return 200."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": source_type},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == source_type
