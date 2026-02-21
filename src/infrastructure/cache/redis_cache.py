"""
Redis Caching Layer for Quality Governance Platform

Features:
- Distributed caching with Redis
- Fallback to in-memory cache
- Configurable TTLs per cache type
- Cache invalidation patterns
- Serialization with JSON and pickle
"""

import asyncio
import hashlib
import json
import logging
import os
import pickle
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheType(Enum):
    """Cache categories with default TTLs."""

    SHORT = 60  # 1 minute - for frequently changing data
    MEDIUM = 300  # 5 minutes - for moderately stable data
    LONG = 3600  # 1 hour - for stable reference data
    DAILY = 86400  # 24 hours - for very stable data
    SESSION = 1800  # 30 minutes - for session data


@dataclass
class CacheConfig:
    """Cache configuration."""

    redis_url: Optional[str] = None
    default_ttl: int = 300
    max_memory_items: int = 1000
    enable_stats: bool = True
    key_prefix: str = "qgp:"


class InMemoryCache:
    """Thread-safe in-memory LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None

            value, expires_at = self._cache[key]

            # Check if expired
            if expires_at and time.time() > expires_at:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return value

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL."""
        async with self._lock:
            # Evict oldest items if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            expires_at = time.time() + ttl if ttl > 0 else None
            self._cache[key] = (value, expires_at)
            self._stats["sets"] += 1
            return True

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats["deletes"] += 1
                return True
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (simple glob)."""
        async with self._lock:
            import fnmatch

            keys_to_delete = [
                k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            self._stats["deletes"] += len(keys_to_delete)
            return len(keys_to_delete)

    async def clear(self) -> bool:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            return True

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        async with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_rate": round(hit_rate * 100, 2),
            }


class RedisCache:
    """Redis-backed cache with connection pooling and retry logic."""

    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 2.0  # seconds; doubles each attempt

    def __init__(self, redis_url: str, key_prefix: str = "qgp:"):
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._redis = None
        self._fallback = InMemoryCache()
        self._use_fallback = False
        self._consecutive_failures = 0

    async def _get_redis(self):
        """Get or create Redis connection with explicit pool config and retry."""
        if self._redis is None and not self._use_fallback:
            try:
                import redis.asyncio as redis
                from redis.asyncio.connection import ConnectionPool

                pool = ConnectionPool.from_url(
                    self._redis_url,
                    max_connections=20,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    decode_responses=False,
                    health_check_interval=30,
                )
                self._redis = redis.Redis(connection_pool=pool)
                await self._redis.ping()
                self._consecutive_failures = 0
            except Exception as e:
                self._consecutive_failures += 1
                print(
                    f"[Cache] Redis connection failed ({self._consecutive_failures}/{self._MAX_RETRIES}): {e}"
                )
                self._redis = None
                if self._consecutive_failures >= self._MAX_RETRIES:
                    print(
                        "[Cache] Max retries reached, falling back to in-memory cache"
                    )
                    self._use_fallback = True
        return self._redis

    async def reconnect(self) -> bool:
        """Attempt to reconnect to Redis after fallback.

        Can be called periodically (e.g. from a health check) to recover
        from transient Redis outages without restarting the process.
        """
        self._use_fallback = False
        self._consecutive_failures = 0
        self._redis = None
        conn = await self._get_redis()
        return conn is not None

    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self._key_prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if self._use_fallback:
            return await self._fallback.get(key)

        redis = await self._get_redis()
        if redis is None:
            return await self._fallback.get(key)

        try:
            data = await redis.get(self._make_key(key))
            if data is None:
                return None
            return json.loads(data)
        except Exception as e:
            print(f"[Cache] Redis get error: {e}")
            return await self._fallback.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in Redis with TTL."""
        if self._use_fallback:
            return await self._fallback.set(key, value, ttl)

        redis = await self._get_redis()
        if redis is None:
            return await self._fallback.set(key, value, ttl)

        try:
            data = json.dumps(value, default=str)
            if ttl > 0:
                await redis.setex(self._make_key(key), ttl, data)
            else:
                await redis.set(self._make_key(key), data)
            return True
        except Exception as e:
            print(f"[Cache] Redis set error: {e}")
            return await self._fallback.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if self._use_fallback:
            return await self._fallback.delete(key)

        redis = await self._get_redis()
        if redis is None:
            return await self._fallback.delete(key)

        try:
            result = await redis.delete(self._make_key(key))
            return result > 0
        except Exception as e:
            print(f"[Cache] Redis delete error: {e}")
            return await self._fallback.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if self._use_fallback:
            return await self._fallback.delete_pattern(pattern)

        redis = await self._get_redis()
        if redis is None:
            return await self._fallback.delete_pattern(pattern)

        try:
            full_pattern = self._make_key(pattern)
            keys = []
            async for key in redis.scan_iter(match=full_pattern):
                keys.append(key)

            if keys:
                await redis.delete(*keys)
            return len(keys)
        except Exception as e:
            print(f"[Cache] Redis delete pattern error: {e}")
            return await self._fallback.delete_pattern(pattern)

    async def clear(self) -> bool:
        """Clear all cache entries with prefix."""
        return await self.delete_pattern("*") > 0

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        if self._use_fallback:
            stats = await self._fallback.get_stats()
            stats["backend"] = "in-memory"
            return stats

        redis = await self._get_redis()
        if redis is None:
            stats = await self._fallback.get_stats()
            stats["backend"] = "in-memory"
            return stats

        try:
            info = await redis.info("stats")
            memory = await redis.info("memory")
            return {
                "backend": "redis",
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "memory_used": memory.get("used_memory_human", "N/A"),
                "connected_clients": (await redis.info("clients")).get(
                    "connected_clients", 0
                ),
            }
        except Exception as e:
            print(f"[Cache] Redis stats error: {e}")
            return {"backend": "redis", "error": str(e)}


# Global cache instance
_cache: Optional[Union[InMemoryCache, RedisCache]] = None


def get_cache() -> Union[InMemoryCache, RedisCache]:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            _cache = RedisCache(redis_url)
        else:
            _cache = InMemoryCache()
    return _cache


async def invalidate_tenant_cache(tenant_id: int | None, entity_type: str) -> int:
    """Invalidate all cached entries for a tenant's entity type.

    Uses pattern-based key deletion for namespace isolation.
    E.g., invalidate_tenant_cache(1, "risks") clears all risk caches for tenant 1.
    """
    cache = get_cache()
    if not isinstance(cache, RedisCache) or not cache._redis:
        return 0

    pattern = f"tenant:{tenant_id}:{entity_type}:*"
    deleted = 0
    async for key in cache._redis.scan_iter(match=pattern):
        await cache._redis.delete(key)
        deleted += 1

    if deleted:
        logger.info(f"Invalidated {deleted} cache keys matching {pattern}")
    return deleted


async def invalidate_entity_cache(entity_type: str, entity_id: int) -> None:
    """Invalidate cache for a specific entity."""
    cache = get_cache()
    if not isinstance(cache, RedisCache) or not cache._redis:
        return

    key = f"{entity_type}:{entity_id}"
    await cache.delete(key)


def make_cache_key(*args, **kwargs) -> str:
    """Create a cache key from function arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)
    return hashlib.md5(
        key_string.encode(), usedforsecurity=False
    ).hexdigest()  # nosec B324


def cached(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
    cache_type: Optional[CacheType] = None,
):
    """
    Decorator for caching function results.

    Usage:
        @cached(ttl=60)
        async def get_user(user_id: int):
            ...

        @cached(cache_type=CacheType.LONG)
        async def get_standards():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cache = get_cache()

            # Build cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            arg_key = make_cache_key(*args, **kwargs)
            cache_key = f"{prefix}:{arg_key}"

            # Check cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            cache_ttl = cache_type.value if cache_type else ttl
            await cache.set(cache_key, result, cache_ttl)

            return result

        # Add cache invalidation helper
        async def invalidate(*args, **kwargs):
            cache = get_cache()
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            arg_key = make_cache_key(*args, **kwargs)
            cache_key = f"{prefix}:{arg_key}"
            await cache.delete(cache_key)

        wrapper.invalidate = invalidate
        wrapper.invalidate_all = lambda: get_cache().delete_pattern(
            f"{key_prefix or func.__module__}.{func.__name__}:*"
        )

        return wrapper

    return decorator


def invalidate_cache(pattern: str):
    """
    Decorator to invalidate cache after function execution.

    Usage:
        @invalidate_cache("users:*")
        async def update_user(user_id: int, data: dict):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            result = await func(*args, **kwargs)
            cache = get_cache()
            await cache.delete_pattern(pattern)
            return result

        return wrapper

    return decorator


# ============================================================================
# Cache Warmup
# ============================================================================


async def warmup_cache():
    """Warm up cache with frequently accessed data."""
    import logging

    logger = logging.getLogger(__name__)
    cache = get_cache()

    if isinstance(cache, RedisCache) and not cache._redis:
        await cache._get_redis()
        if cache._use_fallback:
            logger.warning("Cache warmup skipped: Redis unavailable")
            return

    try:
        from src.infrastructure.database import async_session_maker

        async with async_session_maker() as db:
            from sqlalchemy import select

            from src.domain.models.standard import Standard

            result = await db.execute(select(Standard).limit(100))
            standards = result.scalars().all()
            for std in standards:
                await cache.set(
                    f"standard:{std.id}",
                    {"id": std.id, "name": std.name, "code": std.code},
                    ttl=CacheType.DAILY.value,
                )

            logger.info("Cache warmup complete: %d standards preloaded", len(standards))
    except Exception as e:
        logger.warning("Cache warmup failed: %s", e)


# ============================================================================
# FastAPI Integration
# ============================================================================


from fastapi import APIRouter

from src.api.dependencies import CurrentSuperuser

cache_router = APIRouter(prefix="/cache", tags=["Cache"])


@cache_router.get("/stats")
async def get_cache_stats():
    """Get cache statistics."""
    cache = get_cache()
    return await cache.get_stats()


@cache_router.post("/clear")
async def clear_cache(user: CurrentSuperuser):
    """Clear all cache entries (superuser only)."""
    cache = get_cache()
    await cache.clear()
    return {"success": True, "message": "Cache cleared"}


@cache_router.delete("/{pattern}")
async def invalidate_pattern(pattern: str, user: CurrentSuperuser):
    """Invalidate cache entries matching pattern (superuser only)."""
    cache = get_cache()
    count = await cache.delete_pattern(pattern)
    return {"success": True, "invalidated": count}
