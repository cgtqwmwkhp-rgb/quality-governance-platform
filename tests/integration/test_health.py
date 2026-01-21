"""Integration tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient


def test_health_check(sync_client: TestClient):
    """Test health check endpoint returns healthy status."""
    response = sync_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_check_async(client):
    """Test health check endpoint using async client."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
