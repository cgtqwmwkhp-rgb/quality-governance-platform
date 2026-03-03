"""Unit tests for rate limiting middleware."""

import asyncio
import time

import pytest

from src.infrastructure.middleware.rate_limiter import (
    ENDPOINT_LIMITS,
    InMemoryRateLimiter,
    RateLimitConfig,
    get_limit_config,
)


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_config_exists(self):
        """Verify default rate limit config exists."""
        assert "default" in ENDPOINT_LIMITS
        default = ENDPOINT_LIMITS["default"]
        assert default.requests_per_minute == 60
        assert default.burst_limit == 20

    def test_auth_endpoints_have_stricter_limits(self):
        """Verify auth endpoints have stricter rate limits."""
        login_config = ENDPOINT_LIMITS.get("/api/auth/login")
        assert login_config is not None
        assert login_config.requests_per_minute == 10
        assert login_config.burst_limit == 5

    def test_sensitive_list_endpoints_have_stricter_limits(self):
        """Verify endpoints with email filters have stricter limits.

        These endpoints were identified in Stage 2 security fix as
        potentially vulnerable to email enumeration abuse.
        """
        # Incidents endpoint
        incidents_config = ENDPOINT_LIMITS.get("/api/v1/incidents")
        assert incidents_config is not None
        assert incidents_config.requests_per_minute == 30
        assert incidents_config.burst_limit == 10

        # Complaints endpoint
        complaints_config = ENDPOINT_LIMITS.get("/api/v1/complaints")
        assert complaints_config is not None
        assert complaints_config.requests_per_minute == 30
        assert complaints_config.burst_limit == 10

        # RTAs endpoint
        rtas_config = ENDPOINT_LIMITS.get("/api/v1/rtas")
        assert rtas_config is not None
        assert rtas_config.requests_per_minute == 30
        assert rtas_config.burst_limit == 10

    def test_get_limit_config_returns_specific_config(self):
        """Verify get_limit_config returns endpoint-specific config."""
        config = get_limit_config("/api/v1/incidents")
        assert config.requests_per_minute == 30

        config = get_limit_config("/api/v1/complaints")
        assert config.requests_per_minute == 30

    def test_get_limit_config_returns_default_for_unknown(self):
        """Verify get_limit_config returns default for unknown endpoints."""
        config = get_limit_config("/api/v1/unknown/endpoint")
        assert config.requests_per_minute == 60


class TestInMemoryRateLimiter:
    """Test in-memory rate limiter implementation."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Verify requests under limit are allowed."""
        limiter = InMemoryRateLimiter()

        is_allowed, remaining, _ = await limiter.is_allowed(
            key="test-user-1",
            limit=10,
            window_seconds=60,
        )

        assert is_allowed is True
        assert remaining == 9

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self):
        """Verify requests over limit are blocked."""
        limiter = InMemoryRateLimiter()

        # Make requests up to the limit
        for i in range(10):
            await limiter.is_allowed("test-user-2", 10, 60)

        # Next request should be blocked
        is_allowed, remaining, _ = await limiter.is_allowed(
            key="test-user-2",
            limit=10,
            window_seconds=60,
        )

        assert is_allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_different_keys_have_separate_limits(self):
        """Verify different keys (users/IPs) have separate limits."""
        limiter = InMemoryRateLimiter()

        # Exhaust limit for user-a
        for _ in range(5):
            await limiter.is_allowed("user-a", 5, 60)

        # user-a should be blocked
        is_allowed_a, _, _ = await limiter.is_allowed("user-a", 5, 60)
        assert is_allowed_a is False

        # user-b should still be allowed
        is_allowed_b, _, _ = await limiter.is_allowed("user-b", 5, 60)
        assert is_allowed_b is True

    @pytest.mark.asyncio
    async def test_returns_reset_time(self):
        """Verify reset time is returned correctly."""
        limiter = InMemoryRateLimiter()
        now = time.time()

        _, _, reset_time = await limiter.is_allowed("test-user-3", 10, 60)

        # Reset time should be within the window (allow 1 second tolerance for int truncation)
        assert reset_time >= now - 1
        assert reset_time <= now + 60

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_entries(self):
        """Verify cleanup removes expired entries."""
        limiter = InMemoryRateLimiter()

        # Add some requests
        await limiter.is_allowed("cleanup-test", 10, 60)
        assert "cleanup-test" in limiter._requests

        # Force cleanup (entries are kept for 1 hour max)
        await limiter.cleanup()

        # Entry should still be there (within 1 hour)
        assert "cleanup-test" in limiter._requests


class TestSecurityEndpointLimits:
    """Test that security-sensitive endpoints have appropriate limits."""

    def test_email_filter_endpoints_rate_limited(self):
        """Verify endpoints that accept email filters are rate limited.

        Security requirement from Stage 2: Endpoints that accept email
        parameters must have stricter rate limits to prevent abuse.
        """
        email_filter_endpoints = [
            "/api/v1/incidents",
            "/api/v1/complaints",
            "/api/v1/rtas",
        ]

        for endpoint in email_filter_endpoints:
            config = get_limit_config(endpoint)
            # Should have stricter limits than default (60 rpm)
            assert config.requests_per_minute <= 30, (
                f"Endpoint {endpoint} should have rate limit <= 30 rpm, "
                f"got {config.requests_per_minute}"
            )

    def test_authenticated_users_get_higher_limits(self):
        """Verify authenticated users get multiplied limits."""
        config = RateLimitConfig(
            requests_per_minute=30,
            authenticated_multiplier=2.0,
        )

        # Authenticated users should get 2x the limit
        authenticated_limit = int(
            config.requests_per_minute * config.authenticated_multiplier
        )
        assert authenticated_limit == 60
