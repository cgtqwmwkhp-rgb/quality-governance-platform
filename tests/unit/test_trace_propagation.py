"""Tests for W3C traceparent header propagation through middleware.

Verifies that:
1. Requests with a traceparent header receive a correlation ID in the response.
2. Requests without traceparent still get a generated X-Request-ID.
3. The X-Request-ID header from the client is respected when provided.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app

VALID_TRACEPARENT = "00-4bf92f3577b16e8a3ee7b72d6c2e0e14-b7ad6b7169203331-01"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestTraceparentPropagation:
    """Verify middleware propagates W3C trace context."""

    def test_response_includes_request_id_with_traceparent(self, client):
        """A request carrying traceparent should still receive X-Request-ID."""
        response = client.get(
            "/healthz",
            headers={"traceparent": VALID_TRACEPARENT},
        )
        assert response.status_code == 200
        assert "x-request-id" in response.headers

    def test_response_includes_request_id_without_traceparent(self, client):
        """Requests without traceparent should still get a generated ID."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) > 0

    def test_client_request_id_is_echoed(self, client):
        """X-Request-ID sent by the client should be echoed back."""
        custom_id = "test-trace-abc123"
        response = client.get(
            "/healthz",
            headers={"X-Request-ID": custom_id},
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id

    def test_health_body_contains_request_id(self, client):
        """The /health endpoint body includes the propagated request_id."""
        custom_id = "trace-prop-check-001"
        response = client.get(
            "/health",
            headers={
                "traceparent": VALID_TRACEPARENT,
                "X-Request-ID": custom_id,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["request_id"] == custom_id

    def test_traceparent_does_not_break_normal_responses(self, client):
        """Traceparent header should not cause errors on any endpoint."""
        response = client.get(
            "/api/v1/meta/version",
            headers={"traceparent": VALID_TRACEPARENT},
        )
        assert response.status_code == 200
        assert "build_sha" in response.json()
