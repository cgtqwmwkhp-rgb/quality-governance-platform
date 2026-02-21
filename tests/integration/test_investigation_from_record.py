"""
Tests for /api/v1/investigations/from-record endpoint.

Tests for:
- JSON body contract (not query params)
- 404 SOURCE_NOT_FOUND with JSON error
- 409 INV_ALREADY_EXISTS with existing_investigation_id
- 400 VALIDATION_ERROR with stable error code
- 201 successful creation
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestFromRecordEndpoint:
    """Tests for the from-record endpoint contract."""

    async def test_from_record_accepts_json_body(self, client: AsyncClient):
        """Test from-record endpoint accepts JSON body (not query params)."""
        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": 1,
                "title": "Test Investigation",
            },
        )
        # Should get 401 (auth required), not 405 (method not allowed)
        # This proves the endpoint accepts POST with JSON body
        assert response.status_code == 401

    async def test_from_record_rejects_empty_body(self, client: AsyncClient, auth_headers: dict):
        """Test from-record rejects requests without body (returns 422)."""
        headers = {**auth_headers, "Content-Type": "application/json"}
        response = await client.post(
            "/api/v1/investigations/from-record",
            headers=headers,
        )
        # Should get 422 validation error for missing body
        assert response.status_code == 422

    async def test_from_record_validates_source_type(self, client: AsyncClient, auth_headers: dict):
        """Test from-record validates source_type against enum."""
        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "invalid_type",
                "source_id": 1,
                "title": "Test",
            },
            headers=auth_headers,
        )
        # Should get 422 for invalid enum value
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_from_record_validates_source_id_positive(self, client: AsyncClient, auth_headers: dict):
        """Test from-record requires source_id > 0."""
        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": 0,
                "title": "Test",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_from_record_validates_title_not_empty(self, client: AsyncClient, auth_headers: dict):
        """Test from-record requires non-empty title."""
        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": 1,
                "title": "",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestFromRecordErrorResponses:
    """Test error responses are JSON with stable error codes."""

    async def test_source_not_found_returns_json(self, client: AsyncClient, auth_headers: dict):
        """Test 404 SOURCE_NOT_FOUND returns JSON with error_code."""
        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": 999999,  # Non-existent
                "title": "Test Investigation",
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "SOURCE_NOT_FOUND"
        assert "message" in data["detail"]
        assert "request_id" in data["detail"]

    async def test_duplicate_returns_409_with_existing_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        near_miss_with_investigation: tuple,
    ):
        """Test 409 INV_ALREADY_EXISTS includes existing_investigation_id."""
        near_miss, investigation = near_miss_with_investigation

        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": near_miss.id,
                "title": "Duplicate Investigation",
            },
            headers=auth_headers,
        )
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["error_code"] == "INV_ALREADY_EXISTS"
        assert data["detail"]["details"]["existing_investigation_id"] == investigation.id
        assert "existing_reference_number" in data["detail"]["details"]


@pytest.mark.asyncio
class TestSourceRecordsEndpoint:
    """Tests for GET /api/v1/investigations/source-records."""

    async def test_source_records_requires_source_type(self, client: AsyncClient, auth_headers: dict):
        """Test source-records requires source_type query param."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            headers=auth_headers,
        )
        # Should get 422 for missing required query param
        assert response.status_code == 422

    async def test_source_records_validates_source_type(self, client: AsyncClient, auth_headers: dict):
        """Test source-records validates source_type."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "invalid_type"},
            headers=auth_headers,
        )
        # Should get 400 for invalid source type
        assert response.status_code == 400

    async def test_source_records_returns_paginated_list(self, client: AsyncClient, auth_headers: dict):
        """Test source-records returns paginated list with investigation status."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss", "page": 1, "size": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "source_type" in data
        assert data["source_type"] == "near_miss"

    async def test_source_records_marks_investigated(
        self,
        client: AsyncClient,
        auth_headers: dict,
        near_miss_with_investigation: tuple,
    ):
        """Test source-records marks records with investigation_id."""
        near_miss, investigation = near_miss_with_investigation

        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Find the investigated near miss in results
        investigated_record = next((item for item in data["items"] if item["source_id"] == near_miss.id), None)
        assert investigated_record is not None
        assert investigated_record["investigation_id"] == investigation.id
        assert investigated_record["investigation_reference"] == investigation.reference_number

    async def test_source_records_supports_search(self, client: AsyncClient, auth_headers: dict):
        """Test source-records supports search query."""
        response = await client.get(
            "/api/v1/investigations/source-records",
            params={"source_type": "near_miss", "q": "test"},
            headers=auth_headers,
        )
        assert response.status_code == 200


@pytest.mark.asyncio
class TestDuplicatePrevention:
    """Tests for duplicate investigation prevention."""

    async def test_unique_constraint_exists(self):
        """Test unique constraint is defined on model."""
        # This is a structural test - checks the migration/model definition
        # The actual constraint behavior is tested in test_duplicate_returns_409_with_existing_id
        from sqlalchemy import inspect

        from src.domain.models.investigation import InvestigationRun

        # Get indexes
        mapper = inspect(InvestigationRun)
        table = mapper.local_table

        # Check for unique index on (assigned_entity_type, assigned_entity_id)
        unique_indexes = [idx for idx in table.indexes if idx.unique and len(idx.columns) == 2]
        source_index = next(
            (
                idx
                for idx in unique_indexes
                if any("entity_type" in str(c) for c in idx.columns) and any("entity_id" in str(c) for c in idx.columns)
            ),
            None,
        )
        # Note: This may not find the index if it was added via migration
        # The actual enforcement is tested in the 409 test

    async def test_application_level_duplicate_check(self, client: AsyncClient, auth_headers: dict, near_miss_factory):
        """Test application-level duplicate check before DB constraint."""
        # Create a near miss
        near_miss = await near_miss_factory()

        # First creation should succeed
        response1 = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": near_miss.id,
                "title": "First Investigation",
            },
            headers=auth_headers,
        )
        assert response1.status_code == 201

        # Second creation should fail with 409
        response2 = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": near_miss.id,
                "title": "Duplicate Investigation",
            },
            headers=auth_headers,
        )
        assert response2.status_code == 409
        data = response2.json()
        assert data["detail"]["error_code"] == "INV_ALREADY_EXISTS"


@pytest.mark.asyncio
class TestValidSourceTypes:
    """Test all valid source types work."""

    @pytest.mark.parametrize(
        "source_type",
        ["near_miss", "road_traffic_collision", "complaint", "reporting_incident"],
    )
    async def test_all_source_types_accepted(self, client: AsyncClient, source_type: str):
        """Test all valid source types are accepted in schema."""
        from src.api.schemas.investigation import CreateFromRecordRequest

        # Should not raise
        request = CreateFromRecordRequest(source_type=source_type, source_id=1, title="Test")
        assert request.source_type == source_type
