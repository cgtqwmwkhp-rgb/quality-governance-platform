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


@pytest.mark.asyncio
async def test_meta_version_endpoint(client: AsyncClient):
    """Test /api/v1/meta/version endpoint returns build information.

    This endpoint is used by the deploy workflow to verify the correct
    version is deployed. It must return:
    - build_sha: Git commit SHA from BUILD_SHA env var
    - build_time: Build timestamp from BUILD_TIME env var
    - app_name: Application name
    - environment: Current environment (staging/production)

    No authentication required - this is public deployment metadata.
    """
    response = await client.get("/api/v1/meta/version")

    assert response.status_code == 200
    data = response.json()

    # Required fields for deploy verification
    assert "build_sha" in data
    assert "build_time" in data
    assert "app_name" in data
    assert "environment" in data

    # build_sha should be non-empty (defaults to "dev" in local dev)
    assert len(data["build_sha"]) > 0

    # build_time should be non-empty (defaults to "local" in local dev)
    assert len(data["build_time"]) > 0


@pytest.mark.asyncio
async def test_meta_version_no_auth_required(client: AsyncClient):
    """Verify /api/v1/meta/version is public and does not require auth.

    This endpoint must be accessible without authentication for:
    - Deploy workflow health checks
    - Monitoring and observability tools
    - Runtime version verification
    """
    # Request without any auth headers
    response = await client.get("/api/v1/meta/version")

    # Should return 200, not 401
    assert response.status_code == 200
    assert response.json().get("build_sha") is not None


@pytest.mark.asyncio
async def test_openapi_endpoint_accessible(client: AsyncClient):
    """Test /openapi.json endpoint returns valid OpenAPI spec.

    This endpoint is verified by Deploy Proof v3 for observability.
    The OpenAPI schema is pre-warmed at startup for fast responses.
    """
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()

    # Verify it's a valid OpenAPI 3.x document
    assert "openapi" in data
    assert data["openapi"].startswith("3.")
    assert "info" in data
    assert "paths" in data


@pytest.mark.asyncio
async def test_openapi_cached_fast_response(client: AsyncClient):
    """Verify OpenAPI schema is cached and responds quickly.

    Deploy Proof v3 requirement: OpenAPI should respond within 5s.
    With pre-warming at startup, subsequent requests should be fast (<1s).
    This test verifies the caching mechanism is working.
    """
    import time

    # First request (should already be cached from app startup)
    start = time.perf_counter()
    response1 = await client.get("/openapi.json")
    first_duration = time.perf_counter() - start

    # Second request (definitely from cache)
    start = time.perf_counter()
    response2 = await client.get("/openapi.json")
    second_duration = time.perf_counter() - start

    # Both should succeed
    assert response1.status_code == 200
    assert response2.status_code == 200

    # Second request should be fast (under 2 seconds in CI environment)
    # Note: We use a generous threshold as CI runners vary in performance
    assert (
        second_duration < 2.0
    ), f"Cached OpenAPI took {second_duration:.2f}s, expected <2s"

    # Content should be identical (same cached schema)
    assert response1.json() == response2.json()
