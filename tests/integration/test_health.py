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
    assert "redis" in data


@pytest.mark.asyncio
async def test_readyz_returns_503_when_redis_required_and_missing(client: AsyncClient, monkeypatch):
    """Production (or staging+imports) must fail readiness when REDIS_URL is absent.

    Deploy probes that expect 200 will correctly fail until Redis is configured.
    """
    from src.core.config import settings

    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "app_env", "production")

    response = await client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["redis"] == "not_configured"
    assert settings.is_redis_required is True


@pytest.mark.asyncio
async def test_api_health_readyz_returns_503_when_redis_required_and_missing(client: AsyncClient, monkeypatch):
    """`/api/v1/health/readyz` must match root `/readyz` Redis fail-fast contract."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "app_env", "production")

    response = await client.get("/api/v1/health/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["redis"] == "not_configured"


@pytest.mark.asyncio
async def test_readyz_allows_missing_redis_in_development(client: AsyncClient, monkeypatch):
    """Development may omit Redis; readiness stays non-fatal for redis:not_configured."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "external_audit_import_enabled", False)

    response = await client.get("/readyz")

    # DB may still drive 503; Redis absence alone must not force failure in development.
    data = response.json()
    assert data["redis"] == "not_configured"
    if response.status_code == 200:
        assert data["status"] == "ready"
    else:
        assert response.status_code == 503
        # If not ready, it must be for a non-redis reason (e.g. database).
        assert data.get("database") in {"disconnected", "degraded", "ok", "connected"}


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
    assert second_duration < 2.0, f"Cached OpenAPI took {second_duration:.2f}s, expected <2s"

    # Content should be identical (same cached schema)
    assert response1.json() == response2.json()


@pytest.mark.asyncio
async def test_api_health_readyz_includes_push_vapid_status(client: AsyncClient, monkeypatch):
    """WCS-B06: /api/v1/health/readyz surfaces push/VAPID without failing readiness for missing keys."""
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)

    response = await client.get("/api/v1/health/readyz")
    assert response.status_code in [200, 503]
    data = response.json()
    checks = data.get("checks", data)
    assert "push" in checks
    assert checks["push"] == "not_configured"
    assert "vapid" in checks
    assert checks["vapid"]["status"] == "not_configured"
    assert checks["vapid"]["public_key_present"] is False
    # Missing VAPID must not be the sole reason for 503
    if response.status_code == 503:
        assert checks.get("database") in {"degraded", "disconnected", "ok", "connected"} or checks.get("redis") in {
            "degraded",
            "not_configured",
            "disconnected",
        }


@pytest.mark.asyncio
async def test_root_readyz_includes_push_vapid_status(client: AsyncClient, monkeypatch):
    """WCS-B06: root /readyz also reports push/VAPID readiness fields."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BPublic")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private")

    response = await client.get("/readyz")
    assert response.status_code in [200, 503]
    data = response.json()
    assert data.get("push") == "configured"
    assert data.get("vapid", {}).get("status") == "configured"
    assert data.get("vapid", {}).get("public_key_present") is True


@pytest.mark.asyncio
async def test_root_readyz_includes_email_configured(client: AsyncClient, monkeypatch):
    """Lane 1: /readyz reports email_configured without failing readiness when SMTP missing."""
    monkeypatch.delenv("EMAIL_ENABLED", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    response = await client.get("/readyz")
    assert response.status_code in [200, 503]
    data = response.json()
    assert data.get("email_configured") is False
    assert data.get("email", {}).get("status") == "not_configured"
    assert data.get("email", {}).get("email_enabled") is False


@pytest.mark.asyncio
async def test_api_health_readyz_email_misconfigured_when_enabled(client: AsyncClient, monkeypatch):
    """EMAIL_ENABLED without SMTP is honest misconfigured; readiness HTTP status unchanged."""
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    response = await client.get("/api/v1/health/readyz")
    assert response.status_code in [200, 503]
    checks = response.json().get("checks", {})
    assert checks.get("email_configured") is False
    assert checks.get("email", {}).get("status") == "misconfigured"
    assert checks.get("email", {}).get("email_enabled") is True


@pytest.mark.asyncio
async def test_root_readyz_includes_sms_and_channels(client: AsyncClient, monkeypatch):
    """Lane 1: /readyz reports SMS + channels summary without failing readiness."""
    monkeypatch.delenv("SMS_ENABLED", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)

    response = await client.get("/readyz")
    assert response.status_code in [200, 503]
    data = response.json()
    assert data.get("sms_configured") is False
    assert data.get("sms", {}).get("status") == "not_configured"
    assert data.get("channels", {}).get("email") in {
        "not_configured",
        "misconfigured",
        "credentials_present",
        "configured",
    }
    assert data.get("channels", {}).get("sms") == "not_configured"
    assert data.get("channels", {}).get("push") in {"not_configured", "partial", "configured"}
    assert data.get("channels", {}).get("pagerduty") in {
        "not_configured",
        "misconfigured",
        "credentials_present",
        "configured",
        "send_failed",
    }
    assert "dlq" in data
    assert "depth" in data["dlq"]


@pytest.mark.asyncio
async def test_root_readyz_includes_pagerduty_not_configured(client: AsyncClient, monkeypatch):
    """S12: /readyz reports pagerduty not_configured without inventing secrets or failing closed."""
    monkeypatch.delenv("PAGERDUTY_ENABLED", raising=False)
    monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)

    from src.infrastructure.alerting.pagerduty_client import reset_last_enqueue_status

    reset_last_enqueue_status()

    response = await client.get("/readyz")
    assert response.status_code in [200, 503]
    data = response.json()
    assert data.get("pagerduty_configured") is False
    assert data.get("pagerduty", {}).get("status") == "not_configured"
    assert data.get("pagerduty", {}).get("fail_closed") is False
    assert data.get("channels", {}).get("pagerduty") == "not_configured"
    # Missing PagerDuty must not be the sole reason for 503
    if response.status_code == 503:
        assert data.get("database") in {"disconnected", "degraded", "ok", "connected"} or data.get("redis") in {
            "degraded",
            "not_configured",
            "disconnected",
        }


@pytest.mark.asyncio
async def test_api_health_readyz_pagerduty_send_failed_fail_closed(client: AsyncClient, monkeypatch):
    """S12: when routing key is set and last enqueue failed, readiness fails closed (503)."""
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")

    from src.infrastructure.alerting import pagerduty_client as pd_client

    pd_client.reset_last_enqueue_status()
    pd_client._record("failed", error="PagerDuty Events API HTTP 400: bad key", http_status=400)

    response = await client.get("/api/v1/health/readyz")
    assert response.status_code == 503
    checks = response.json().get("checks", {})
    assert checks.get("pagerduty", {}).get("status") == "send_failed"
    assert checks.get("pagerduty", {}).get("fail_closed") is True
    assert checks.get("channels", {}).get("pagerduty") == "send_failed"
    assert "rk-test" not in str(checks)

    pd_client.reset_last_enqueue_status()
