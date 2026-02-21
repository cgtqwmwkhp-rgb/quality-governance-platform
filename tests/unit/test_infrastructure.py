"""
Comprehensive Unit Tests for Infrastructure Components

Target: 90%+ code coverage for infrastructure
"""

import asyncio
import os
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Rate Limiter Tests
# ============================================================================


class TestRateLimiter:
    """Unit tests for rate limiting infrastructure."""

    def test_rate_limiter_import(self):
        """Rate limiter can be imported."""
        from src.infrastructure.middleware.rate_limiter import InMemoryRateLimiter, RateLimitConfig, get_rate_limiter

        assert get_rate_limiter is not None
        assert InMemoryRateLimiter is not None
        assert RateLimitConfig is not None

    def test_rate_limit_config_defaults(self):
        """Rate limit config has sensible defaults."""
        from src.infrastructure.middleware.rate_limiter import RateLimitConfig

        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10

    def test_in_memory_limiter_creation(self):
        """In-memory limiter can be created."""
        from src.infrastructure.middleware.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()
        assert limiter is not None

    @pytest.mark.asyncio
    async def test_in_memory_limiter_allows_requests(self):
        """In-memory limiter allows requests within limit."""
        from src.infrastructure.middleware.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        # First request should be allowed
        allowed, remaining, reset = await limiter.is_allowed("test_key", 10, 60)
        assert allowed is True
        assert remaining >= 0

    @pytest.mark.asyncio
    async def test_in_memory_limiter_blocks_excess(self):
        """In-memory limiter blocks requests over limit."""
        from src.infrastructure.middleware.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        # Make requests up to the limit
        for _ in range(5):
            await limiter.is_allowed("test_key", 5, 60)

        # Next request should be blocked
        allowed, remaining, reset = await limiter.is_allowed("test_key", 5, 60)
        assert allowed is False


# ============================================================================
# Cache Tests
# ============================================================================


class TestRedisCache:
    """Unit tests for caching infrastructure."""

    def test_cache_import(self):
        """Cache can be imported."""
        from src.infrastructure.cache.redis_cache import CacheType, InMemoryCache, cached, get_cache

        assert get_cache is not None
        assert InMemoryCache is not None
        assert CacheType is not None
        assert cached is not None

    def test_cache_type_enum(self):
        """Cache type enum has expected values."""
        from src.infrastructure.cache.redis_cache import CacheType

        assert hasattr(CacheType, "SHORT")
        assert hasattr(CacheType, "MEDIUM")
        assert hasattr(CacheType, "LONG")
        assert hasattr(CacheType, "DAILY")
        assert CacheType.SHORT.value == 60
        assert CacheType.MEDIUM.value == 300
        assert CacheType.LONG.value == 3600

    def test_in_memory_cache_creation(self):
        """In-memory cache can be created."""
        from src.infrastructure.cache.redis_cache import InMemoryCache

        cache = InMemoryCache(max_size=100)
        assert cache is not None
        assert cache._max_size == 100

    @pytest.mark.asyncio
    async def test_in_memory_cache_set_get(self):
        """In-memory cache set and get work."""
        from src.infrastructure.cache.redis_cache import InMemoryCache

        cache = InMemoryCache()

        # Set a value
        await cache.set("test_key", "test_value", ttl=60)

        # Get the value
        value = await cache.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_in_memory_cache_delete(self):
        """In-memory cache delete works."""
        from src.infrastructure.cache.redis_cache import InMemoryCache

        cache = InMemoryCache()

        await cache.set("test_key", "test_value", ttl=60)
        await cache.delete("test_key")

        value = await cache.get("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_in_memory_cache_stats(self):
        """In-memory cache stats work."""
        from src.infrastructure.cache.redis_cache import InMemoryCache

        cache = InMemoryCache()

        await cache.set("key1", "value1", ttl=60)
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = await cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats


# ============================================================================
# Monitoring Tests
# ============================================================================


class TestMonitoring:
    """Unit tests for monitoring infrastructure."""

    def test_monitoring_import(self):
        """Monitoring module can be imported."""
        from src.infrastructure.monitoring.azure_monitor import get_tracer, logger, setup_telemetry, track_metric

        assert logger is not None
        assert setup_telemetry is not None
        assert track_metric is not None
        assert get_tracer is not None

    def test_setup_telemetry_without_app(self):
        """setup_telemetry works without a FastAPI app."""
        from src.infrastructure.monitoring.azure_monitor import setup_telemetry

        setup_telemetry(app=None, service_name="test-service")

    def test_track_metric_before_init(self):
        """track_metric does not raise before telemetry is initialized."""
        from src.infrastructure.monitoring.azure_monitor import track_metric

        track_metric("test.counter", 1.0)

    def test_get_tracer(self):
        """get_tracer returns a tracer instance."""
        from src.infrastructure.monitoring.azure_monitor import get_tracer

        tracer = get_tracer()
        assert tracer is not None


# ============================================================================
# Database Tests
# ============================================================================


class TestDatabase:
    """Unit tests for database infrastructure."""

    def test_database_import(self):
        """Database module can be imported."""
        from src.infrastructure.database import Base

        assert Base is not None

    def test_base_model_metadata(self):
        """Base model has metadata."""
        from src.infrastructure.database import Base

        assert hasattr(Base, "metadata")


# ============================================================================
# WebSocket Tests
# ============================================================================


class TestWebSocket:
    """Unit tests for WebSocket infrastructure."""

    def test_websocket_import(self):
        """WebSocket module can be imported."""
        from src.infrastructure.websocket.connection_manager import ConnectionManager

        assert ConnectionManager is not None

    def test_connection_manager_creation(self):
        """Connection manager can be created."""
        from src.infrastructure.websocket.connection_manager import ConnectionManager

        manager = ConnectionManager()
        assert manager is not None


# ============================================================================
# API Dependencies Tests
# ============================================================================


class TestAPIDependencies:
    """Unit tests for API dependencies."""

    def test_dependencies_import(self):
        """Dependencies can be imported."""
        from src.api.dependencies import DbSession, get_db

        assert get_db is not None
        assert DbSession is not None


# ============================================================================
# Schema Tests
# ============================================================================


class TestSchemas:
    """Unit tests for Pydantic schemas."""

    def test_incident_schemas_import(self):
        """Incident schemas can be imported."""
        from src.api.schemas.incident import IncidentCreate, IncidentUpdate

        assert IncidentCreate is not None
        assert IncidentUpdate is not None

    def test_risk_schemas_import(self):
        """Risk schemas can be imported."""
        from src.api.schemas.risk import RiskCreate, RiskUpdate

        assert RiskCreate is not None
        assert RiskUpdate is not None

    def test_audit_schemas_import(self):
        """Audit schemas can be imported."""
        from src.api.schemas.audit import AuditTemplateCreate

        assert AuditTemplateCreate is not None

    def test_user_schemas_import(self):
        """User schemas can be imported."""
        from src.api.schemas.user import UserCreate

        assert UserCreate is not None


# ============================================================================
# Utility Function Tests
# ============================================================================


class TestUtilities:
    """Unit tests for utility functions."""

    def test_make_cache_key(self):
        """Cache key generation works."""
        from src.infrastructure.cache.redis_cache import make_cache_key

        key1 = make_cache_key("arg1", "arg2", kwarg1="value1")
        key2 = make_cache_key("arg1", "arg2", kwarg1="value1")
        key3 = make_cache_key("different")

        assert key1 == key2
        assert key1 != key3

    def test_client_identifier(self):
        """Client identifier extraction works."""
        from src.infrastructure.middleware.rate_limiter import get_client_identifier

        # Create a mock request
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "127.0.0.1"

        identifier = get_client_identifier(mock_request)
        assert "ip:" in identifier or "user:" in identifier


# ============================================================================
# Configuration Tests
# ============================================================================


class TestConfiguration:
    """Unit tests for configuration."""

    def test_environment_variable_access(self):
        """Environment variables can be accessed."""
        # This should not raise
        value = os.getenv("NONEXISTENT_VAR", "default")
        assert value == "default"

    def test_ai_config_creation(self):
        """AI config can be created."""
        from src.domain.services.ai_models import AIConfig

        config = AIConfig()
        assert config is not None

    def test_ai_config_from_env(self):
        """AI config can be loaded from environment."""
        from src.domain.services.ai_models import AIConfig

        config = AIConfig.from_env()
        assert config is not None


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Unit tests for error handling."""

    def test_http_exception_import(self):
        """HTTP exceptions can be imported."""
        from fastapi import HTTPException

        exception = HTTPException(status_code=404, detail="Not found")
        assert exception.status_code == 404
        assert exception.detail == "Not found"

    def test_validation_error_handling(self):
        """Validation errors are properly handled."""
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            value: int

        with pytest.raises(ValidationError):
            TestModel(value="not_an_int")


# ============================================================================
# Async Tests
# ============================================================================


class TestAsyncOperations:
    """Unit tests for async operations."""

    @pytest.mark.asyncio
    async def test_async_function_execution(self):
        """Async functions execute correctly."""

        async def sample_async():
            await asyncio.sleep(0.01)
            return "completed"

        result = await sample_async()
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_async_generator(self):
        """Async generators work correctly."""

        async def sample_generator():
            for i in range(3):
                yield i

        results = []
        async for value in sample_generator():
            results.append(value)

        assert results == [0, 1, 2]
