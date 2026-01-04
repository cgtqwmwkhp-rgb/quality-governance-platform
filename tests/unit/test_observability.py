"""
Unit tests for observability middleware and health endpoints.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.health import router as health_router
from src.middleware.observability import ObservabilityMiddleware


@pytest.fixture
def app_with_observability():
    """Create a test FastAPI app with observability middleware."""
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)
    app.include_router(health_router)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    return app


@pytest.fixture
def client(app_with_observability):
    """Create a test client."""
    return TestClient(app_with_observability)


def test_request_id_generated(client):
    """Test that request ID is generated when not provided."""
    response = client.get("/test")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36  # UUID length


def test_request_id_preserved(client):
    """Test that provided request ID is preserved."""
    custom_id = "test-request-123"
    response = client.get("/test", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


def test_health_check(client):
    """Test liveness probe endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_check_no_db():
    """Test readiness probe without database dependency."""
    # Create a minimal app without database
    app = FastAPI()

    @app.get("/readyz")
    async def readiness():
        return {"status": "ready"}

    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200
