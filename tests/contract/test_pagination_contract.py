"""Contract tests for list-endpoint pagination response shape."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _assert_list_pagination_shape(data: object) -> None:
    """Accept page-based (page, page_size) or offset-based (skip, limit) pagination."""
    assert isinstance(data, dict), "List response must be a JSON object"
    assert "items" in data, "List response must include 'items'"
    assert "total" in data, "List response must include 'total'"
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)

    has_page_style = "page" in data and "page_size" in data
    has_offset_style = "skip" in data and "limit" in data
    assert (
        has_page_style or has_offset_style
    ), "List response must include either (page, page_size) or (skip, limit) alongside items/total"


@pytest.fixture(scope="module")
def test_client() -> TestClient:
    from src.main import app

    return TestClient(app)


class TestPaginationContract:
    """List endpoints must return a consistent pagination envelope."""

    def test_policies_list_pagination_shape(
        self, test_client: TestClient, optional_auth_headers: dict[str, str]
    ) -> None:
        if not optional_auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/policies", headers=optional_auth_headers)
        assert response.status_code == 200
        _assert_list_pagination_shape(response.json())

    def test_incidents_list_pagination_shape(
        self, test_client: TestClient, optional_auth_headers: dict[str, str]
    ) -> None:
        if not optional_auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/incidents/", headers=optional_auth_headers)
        assert response.status_code == 200
        _assert_list_pagination_shape(response.json())
