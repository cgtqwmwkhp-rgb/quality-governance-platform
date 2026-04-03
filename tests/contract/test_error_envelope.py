"""Contract tests for the canonical API error JSON envelope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _assert_canonical_error_envelope(payload: object) -> None:
    assert isinstance(payload, dict), "Error response body must be a JSON object"
    assert "error" in payload, "Response must use nested 'error' object"
    err = payload["error"]
    assert isinstance(err, dict), "error must be an object"
    for key in ("code", "message", "details", "request_id"):
        assert key in err, f"error.{key} is required"
    assert isinstance(err["code"], str)
    assert isinstance(err["message"], str)
    assert isinstance(err["details"], dict)
    assert isinstance(err["request_id"], str)
    assert err["request_id"], "request_id must be non-empty"


@pytest.fixture(scope="module")
def test_client() -> TestClient:
    from src.main import app

    return TestClient(app)


class TestErrorEnvelopeContract:
    """Error responses must match the platform envelope shape."""

    def test_404_returns_canonical_envelope(
        self, test_client: TestClient, optional_auth_headers: dict[str, str]
    ) -> None:
        if not optional_auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.get("/api/v1/incidents/999999", headers=optional_auth_headers)
        assert response.status_code == 404
        _assert_canonical_error_envelope(response.json())

    def test_422_returns_canonical_envelope(
        self, test_client: TestClient, optional_auth_headers: dict[str, str]
    ) -> None:
        if not optional_auth_headers:
            pytest.skip("Auth not available in test environment")
        response = test_client.post("/api/v1/incidents/", json={}, headers=optional_auth_headers)
        assert response.status_code == 422
        data = response.json()
        _assert_canonical_error_envelope(data)
        assert "errors" in data["error"]["details"]

    def test_401_returns_canonical_envelope(self, test_client: TestClient) -> None:
        response = test_client.get(
            "/api/v1/policies",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401
        _assert_canonical_error_envelope(response.json())
