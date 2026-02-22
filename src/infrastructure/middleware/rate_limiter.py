"""
Rate Limiting Middleware for FastAPI

Features:
- Configurable rate limits per endpoint
- IP-based and user-based limiting
- Redis backend for distributed rate limiting
- Graceful fallback to in-memory when Redis unavailable
- Different limits for authenticated vs anonymous users
"""

import asyncio
import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute
from sqlalchemy import select


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    authenticated_multiplier: float = 2.0  # Authenticated users get 2x limits


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window algorithm."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed and return remaining quota.

        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Clean old requests
            self._requests[key] = [ts for ts in self._requests[key] if ts > window_start]

            current_count = len(self._requests[key])
            remaining = max(0, limit - current_count)
            reset_time = int(window_start + window_seconds)

            if current_count >= limit:
                return False, 0, reset_time

            self._requests[key].append(now)
            return True, remaining - 1, reset_time

    async def cleanup(self):
        """Remove expired entries."""
        async with self._lock:
            now = time.time()
            for key in list(self._requests.keys()):
                self._requests[key] = [ts for ts in self._requests[key] if ts > now - 3600]
                if not self._requests[key]:
                    del self._requests[key]


class RedisRateLimiter:
    """Redis-backed rate limiter for distributed deployments."""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None
        self._fallback = InMemoryRateLimiter()

    async def _get_redis(self):
        """Lazy-load Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(self._redis_url)
                await self._redis.ping()
            except Exception as e:
                print(f"[RateLimit] Redis unavailable, using in-memory: {e}")
                self._redis = None
        return self._redis

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """Check if request is allowed using Redis sliding window."""
        redis = await self._get_redis()

        if redis is None:
            return await self._fallback.is_allowed(key, limit, window_seconds)

        try:
            now = time.time()
            window_start = now - window_seconds
            redis_key = f"ratelimit:{key}"

            # Use pipeline for atomic operations
            pipe = redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds)

            results = await pipe.execute()
            current_count = results[1]

            remaining = max(0, limit - current_count)
            reset_time = int(window_start + window_seconds)

            if current_count >= limit:
                return False, 0, reset_time

            return True, remaining - 1, reset_time

        except Exception as e:
            print(f"[RateLimit] Redis error, falling back: {e}")
            return await self._fallback.is_allowed(key, limit, window_seconds)


# Global rate limiter instance
_rate_limiter: Optional[InMemoryRateLimiter | RedisRateLimiter] = None


def get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        from src.core.config import settings

        if settings.redis_url:
            _rate_limiter = RedisRateLimiter(settings.redis_url)
        else:
            _rate_limiter = InMemoryRateLimiter()
    return _rate_limiter


def get_client_identifier(request: Request) -> str:
    """Get unique identifier for rate limiting."""
    # Try to get user ID from auth token
    user_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from src.core.security import decode_token

            token = auth_header[7:]
            payload = decode_token(token)
            if payload:
                user_id = payload.get("sub")
        except Exception:
            pass

    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


def get_endpoint_key(request: Request) -> str:
    """Get endpoint identifier for rate limiting."""
    path = request.url.path
    method = request.method
    # Normalize path parameters
    normalized = hashlib.md5(f"{method}:{path}".encode(), usedforsecurity=False).hexdigest()[:8]  # nosec B324
    return normalized


# Tenant tier rate limits (requests per minute)
TENANT_TIER_LIMITS = {
    "free": 100,       # 100 req/min
    "standard": 500,   # 500 req/min
    "enterprise": 2000, # 2000 req/min
}

# Cache for tenant tier lookups (tenant_id -> (tier, timestamp))
_tenant_tier_cache: dict[int, tuple[str, float]] = {}
_cache_ttl = 300  # 5 minutes


async def get_tenant_tier(tenant_id: int) -> str:
    """
    Get tenant subscription tier from database with caching.
    
    Args:
        tenant_id: The tenant ID to look up
        
    Returns:
        Subscription tier string (defaults to "standard" if not found)
    """
    # Check cache first
    now = time.time()
    if tenant_id in _tenant_tier_cache:
        tier, cached_time = _tenant_tier_cache[tenant_id]
        if now - cached_time < _cache_ttl:
            return tier
        # Cache expired, remove it
        del _tenant_tier_cache[tenant_id]
    
    # Query database
    try:
        from src.infrastructure.database import async_session_maker
        from src.domain.models.tenant import Tenant
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(Tenant.subscription_tier).where(Tenant.id == tenant_id)
            )
            tier = result.scalar_one_or_none()
            
            if tier:
                # Cache the result
                _tenant_tier_cache[tenant_id] = (tier, now)
                return tier
    except Exception as e:
        # Log error but don't fail - fall back to default
        print(f"[RateLimit] Error looking up tenant tier: {e}")
    
    # Default to "standard" if not found or on error
    default_tier = "standard"
    _tenant_tier_cache[tenant_id] = (default_tier, now)
    return default_tier


# Rate limit configurations by endpoint pattern
ENDPOINT_LIMITS: dict[str, RateLimitConfig] = {
    # Authentication - strict limits
    "/api/v1/auth/login": RateLimitConfig(requests_per_minute=10, burst_limit=5),
    "/api/v1/auth/register": RateLimitConfig(requests_per_minute=5, burst_limit=2),
    "/api/v1/auth/password-reset/request": RateLimitConfig(requests_per_minute=3, burst_limit=2),
    # Security-sensitive list endpoints with email filters - stricter limits
    # These endpoints accept email filters which could be abused for enumeration
    "/api/v1/incidents": RateLimitConfig(requests_per_minute=30, burst_limit=10),
    "/api/v1/complaints": RateLimitConfig(requests_per_minute=30, burst_limit=10),
    "/api/v1/rtas": RateLimitConfig(requests_per_minute=30, burst_limit=10),
    # Portal endpoints - moderate limits
    "/api/portal/": RateLimitConfig(requests_per_minute=30, burst_limit=10),
    # Standard API - default limits
    "default": RateLimitConfig(requests_per_minute=60, burst_limit=20),
    # High-frequency endpoints - higher limits
    "/api/notifications/": RateLimitConfig(requests_per_minute=120, burst_limit=30),
    "/api/realtime/": RateLimitConfig(requests_per_minute=300, burst_limit=50),
    # Dashboard endpoints - read-only, cacheable, higher limits
    "/api/v1/planet-mark/dashboard": RateLimitConfig(requests_per_minute=120, burst_limit=30),
    "/api/v1/uvdb/dashboard": RateLimitConfig(requests_per_minute=120, burst_limit=30),
    # Telemetry - fire-and-forget, needs high limits for batch events
    "/api/v1/telemetry/": RateLimitConfig(requests_per_minute=300, burst_limit=100),
}


def get_limit_config(path: str) -> RateLimitConfig:
    """Get rate limit configuration for a path."""
    for pattern, config in ENDPOINT_LIMITS.items():
        if pattern != "default" and path.startswith(pattern):
            return config
    return ENDPOINT_LIMITS["default"]


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """
    Rate limiting middleware for FastAPI.

    Adds X-RateLimit headers to responses:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining in window
    - X-RateLimit-Reset: Unix timestamp when limit resets
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/api/health", "/ready"]:
        return await call_next(request)

    # Skip rate limiting for CORS preflight requests (OPTIONS)
    # These must pass through to CORSMiddleware without interference
    if request.method == "OPTIONS":
        return await call_next(request)

    limiter = get_rate_limiter()
    client_id = get_client_identifier(request)
    endpoint_key = get_endpoint_key(request)
    config = get_limit_config(request.url.path)

    # Extract tenant_id from request
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # If not in request.state, try to get from JWT payload
    if tenant_id is None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.core.security import decode_token
                token = auth_header[7:]
                payload = decode_token(token)
                if payload:
                    tenant_id = payload.get("tenant_id")
            except Exception:
                pass
    
    # Authenticated users get higher limits
    is_authenticated = client_id.startswith("user:")
    limit = config.requests_per_minute
    if is_authenticated:
        limit = int(limit * config.authenticated_multiplier)

    # Apply tenant-level rate limits if tenant_id is available
    tenant_limit = None
    if tenant_id:
        try:
            tenant_tier = await get_tenant_tier(tenant_id)
            tenant_limit = TENANT_TIER_LIMITS.get(tenant_tier, TENANT_TIER_LIMITS["standard"])
            # Use the minimum of per-user limit and tenant limit
            limit = min(limit, tenant_limit)
        except Exception as e:
            # If tenant lookup fails, continue with per-user limits
            print(f"[RateLimit] Error applying tenant limits: {e}")

    # Create composite key: {tenant_id}:{client_id}:{endpoint_key}
    # Use "no-tenant" if tenant_id is not available
    tenant_key = str(tenant_id) if tenant_id else "no-tenant"
    rate_key = f"{tenant_key}:{client_id}:{endpoint_key}"

    # Check rate limit
    is_allowed, remaining, reset_time = await limiter.is_allowed(
        key=rate_key,
        limit=limit,
        window_seconds=60,
    )

    if not is_allowed:
        return Response(
            content='{"detail": "Rate limit exceeded. Please try again later."}',
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            media_type="application/json",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(max(1, reset_time - int(time.time()))),
            },
        )

    # Process request
    response = await call_next(request)

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_time)

    return response


def rate_limit(
    requests_per_minute: int = 60,
    burst_limit: int = 10,
):
    """
    Decorator for custom rate limiting on specific endpoints.

    Usage:
        @router.get("/expensive-operation")
        @rate_limit(requests_per_minute=10, burst_limit=3)
        async def expensive_operation():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                limiter = get_rate_limiter()
                client_id = get_client_identifier(request)
                func_key = f"{func.__module__}.{func.__name__}"
                rate_key = f"{client_id}:{func_key}"

                is_allowed, remaining, reset_time = await limiter.is_allowed(
                    key=rate_key,
                    limit=requests_per_minute,
                    window_seconds=60,
                )

                if not is_allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded for this operation.",
                        headers={
                            "Retry-After": str(max(1, reset_time - int(time.time()))),
                        },
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class RateLimitedRoute(APIRoute):
    """Custom APIRoute class with built-in rate limiting."""

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def rate_limited_handler(request: Request) -> Response:
            limiter = get_rate_limiter()
            client_id = get_client_identifier(request)
            rate_key = f"{client_id}:{self.path}"

            is_allowed, remaining, reset_time = await limiter.is_allowed(
                key=rate_key,
                limit=60,
                window_seconds=60,
            )

            if not is_allowed:
                return Response(
                    content='{"detail": "Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                )

            response = await original_route_handler(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

        return rate_limited_handler
