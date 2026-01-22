"""Integration tests for health endpoint.

Note: All tests use async client to avoid event loop conflicts between
sync TestClient and async fixtures (asyncpg pool, etc.). See GOVPLAT-ASYNC-001.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_check_request_id(client: AsyncClient):
    """Test health check returns request_id for traceability."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert len(data["request_id"]) > 0


@pytest.mark.asyncio
async def test_healthz_liveness(client: AsyncClient):
    """Test /healthz liveness probe endpoint."""
    response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "request_id" in data


@pytest.mark.asyncio
async def test_readyz_readiness(client: AsyncClient):
    """Test /readyz readiness probe endpoint."""
    response = await client.get("/readyz")

    # May return 200 (ready) or 503 (not ready) depending on DB
    # But should not return 401 or 500
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "request_id" in data
