"""Integration tests for health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint returns healthy status."""
    response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
