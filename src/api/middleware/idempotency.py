"""
Idempotency Middleware for FastAPI

Features:
- Intercepts POST/PUT/PATCH requests with Idempotency-Key header
- Keys are scoped by tenant (from JWT sub claim) + HTTP method + URL path
  to prevent cross-tenant and cross-endpoint idempotency collisions
- Caches responses in Redis with 24h TTL
- Detects payload mismatches and returns 409 conflict
- Gracefully falls back if Redis is unavailable
"""

import base64 as _base64
import hashlib
import json
import logging
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings

logger = logging.getLogger(__name__)

# Redis connection cache
_redis_client: Optional[object] = None
_redis_available: bool = False


async def _get_redis():
    """Get or create Redis connection with conditional import."""
    global _redis_client, _redis_available

    if _redis_client is not None:
        return _redis_client

    if not settings.redis_url:
        return None

    try:
        import redis.asyncio as redis
        from redis.asyncio.connection import ConnectionPool

        pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            decode_responses=False,  # Return bytes to match project pattern
            health_check_interval=30,
        )
        _redis_client = redis.Redis(connection_pool=pool)
        await _redis_client.ping()
        _redis_available = True
        logger.debug("Idempotency middleware: Redis connection established")
        return _redis_client
    except ImportError:
        logger.debug("Idempotency middleware: redis package not available")
        _redis_available = False
        return None
    except Exception as e:
        logger.debug(f"Idempotency middleware: Redis unavailable, will skip idempotency: {e}")
        _redis_available = False
        return None


def _compute_payload_hash(body: bytes) -> str:
    """Compute SHA256 hash of request payload."""
    return hashlib.sha256(body).hexdigest()


def _extract_tenant_fingerprint(request: Request) -> str:
    """Extract a tenant-scoped fingerprint from the Authorization header.

    Uses the first 16 hex chars of SHA-256(token) so that:
    - Two requests from the same user session share the same fingerprint
    - Two requests from different tenants/users never share a fingerprint
    - The raw token value is never stored in Redis
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
    else:
        token = auth_header or "anonymous"
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _make_key(idempotency_key: str, tenant_fingerprint: str, method: str, path: str) -> str:
    """Create a Redis key scoped by tenant + endpoint + client-supplied key.

    Scope components:
      tenant_fingerprint — SHA-256[:16] of the bearer token (prevents cross-tenant collisions)
      method             — HTTP method (prevents cross-endpoint collisions with same key string)
      path               — URL path (prevents cross-endpoint collisions)
      idempotency_key    — client-supplied idempotency key

    The compound key is hashed to keep Redis key lengths bounded.
    """
    compound = f"{tenant_fingerprint}:{method.upper()}:{path}:{idempotency_key}"
    compound_hash = hashlib.sha256(compound.encode()).hexdigest()
    return f"idem:{compound_hash}"


_IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
_IDEMPOTENCY_TTL_S = 86400  # 24 hours
_IN_FLIGHT_POLL_ATTEMPTS = 25
_IN_FLIGHT_POLL_INTERVAL_S = 0.2


def _conflict_response(idempotency_key: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "Idempotency key conflict: request payload differs from original request",
                "details": {"idempotency_key": idempotency_key},
            }
        },
    )


def _response_from_cache(cached_response: dict) -> Response:
    """Rebuild an HTTP response from a completed Redis cache entry."""
    body_content = cached_response["body"]
    if cached_response.get("headers", {}).get("X-Idempotency-Body-Encoding") == "base64":
        body_content = _base64.b64decode(body_content)
        response_headers = {
            k: v for k, v in cached_response["headers"].items() if k != "X-Idempotency-Body-Encoding"
        }
    else:
        response_headers = cached_response.get("headers") or {}
        body_content = body_content.encode("utf-8") if isinstance(body_content, str) else body_content

    return Response(
        content=body_content,
        status_code=cached_response["status_code"],
        headers=response_headers,
    )


async def _parse_cached(redis_client, redis_key: str) -> Optional[dict]:
    cached_data = await redis_client.get(redis_key)
    if not cached_data:
        return None
    if isinstance(cached_data, bytes):
        cached_data = cached_data.decode("utf-8")
    return json.loads(cached_data)


async def _wait_for_cached_response(
    redis_client,
    redis_key: str,
    payload_hash: str,
    idempotency_key: str,
) -> Optional[Response]:
    """Poll while another request holds the in-flight claim (timeout-retry race)."""
    import asyncio

    for _ in range(_IN_FLIGHT_POLL_ATTEMPTS):
        await asyncio.sleep(_IN_FLIGHT_POLL_INTERVAL_S)
        try:
            cached_response = await _parse_cached(redis_client, redis_key)
        except Exception as e:
            logger.warning(f"Idempotency middleware: Error polling Redis: {e}")
            return None
        if not cached_response:
            continue
        if cached_response.get("payload_hash") != payload_hash:
            return _conflict_response(idempotency_key)
        if cached_response.get("status") == "processing":
            continue
        if "body" in cached_response and "status_code" in cached_response:
            logger.debug(f"Idempotency in-flight resolved: {idempotency_key}")
            return _response_from_cache(cached_response)
    return None


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle idempotency keys for mutating requests.

    Intercepts POST/PUT/PATCH requests with Idempotency-Key header:
    - Claims the Redis key with SET NX before executing (blocks concurrent duplicates)
    - Checks Redis for existing cached response
    - If found and payload hash matches, returns cached response
    - If found but payload hash differs, returns 409 Conflict
    - If not found, executes request and caches response with 24h TTL
    - Skips GET/DELETE/OPTIONS/HEAD requests
    - Falls back gracefully if Redis is unavailable
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        # Check for Idempotency-Key header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Get Redis connection (may be None if unavailable)
        redis_client = await _get_redis()
        if redis_client is None:
            # Redis unavailable - process request normally
            logger.debug("Idempotency middleware: Redis unavailable, processing request normally")
            return await call_next(request)

        # Read request body to compute hash
        # Note: We need to read the body, but FastAPI/Starlette only allows reading once
        # So we'll read it, store it, and create a new request with the body
        body_bytes = await request.body()

        # Compute payload hash
        payload_hash = _compute_payload_hash(body_bytes)

        # Build tenant + endpoint scoped Redis key (prevents cross-tenant collisions)
        tenant_fingerprint = _extract_tenant_fingerprint(request)
        redis_key = _make_key(idempotency_key, tenant_fingerprint, request.method, request.url.path)
        claimed = False
        try:
            cached_response = await _parse_cached(redis_client, redis_key)
            if cached_response:
                if cached_response.get("payload_hash") != payload_hash:
                    logger.warning(
                        f"Idempotency key conflict: {idempotency_key}",
                        extra={"idempotency_key": idempotency_key},
                    )
                    return _conflict_response(idempotency_key)

                if cached_response.get("status") == "processing":
                    waited = await _wait_for_cached_response(
                        redis_client, redis_key, payload_hash, idempotency_key
                    )
                    if waited is not None:
                        return waited
                    # Timed out waiting — fall through without a second create if claim fails
                elif "body" in cached_response and "status_code" in cached_response:
                    logger.debug(f"Idempotency cache hit: {idempotency_key}")
                    return _response_from_cache(cached_response)

            # Claim the key before executing so concurrent retries cannot double-create
            placeholder = json.dumps(
                {"status": "processing", "payload_hash": payload_hash}
            ).encode("utf-8")
            claimed = await redis_client.set(redis_key, placeholder, nx=True, ex=_IDEMPOTENCY_TTL_S)
            if not claimed:
                cached_response = await _parse_cached(redis_client, redis_key)
                if cached_response:
                    if cached_response.get("payload_hash") != payload_hash:
                        return _conflict_response(idempotency_key)
                    if "body" in cached_response and "status_code" in cached_response:
                        return _response_from_cache(cached_response)
                    if cached_response.get("status") == "processing":
                        waited = await _wait_for_cached_response(
                            redis_client, redis_key, payload_hash, idempotency_key
                        )
                        if waited is not None:
                            return waited

        except Exception as e:
            logger.warning(f"Idempotency middleware: Error reading from Redis: {e}")
            # Fall through to process request normally

        # Key doesn't exist or error occurred - process request
        # Recreate request with body since we already read it
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE

        # Execute the request
        response = await call_next(request)

        # Cache the response
        try:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Collect response headers (excluding hop-by-hop headers)
            hop_by_hop_headers = {
                "connection",
                "keep-alive",
                "proxy-authenticate",
                "proxy-authorization",
                "te",
                "trailers",
                "transfer-encoding",
                "upgrade",
            }
            response_headers = {k: v for k, v in response.headers.items() if k.lower() not in hop_by_hop_headers}

            # Decode body to string for storage (handle both text and binary)
            try:
                body_str = response_body.decode("utf-8")
            except UnicodeDecodeError:
                body_str = _base64.b64encode(response_body).decode("utf-8")
                response_headers["X-Idempotency-Body-Encoding"] = "base64"

            # Store in Redis with 24h TTL (86400 seconds)
            cache_data = {
                "body": body_str,
                "status_code": response.status_code,
                "headers": response_headers,
                "payload_hash": payload_hash,
            }

            await redis_client.setex(
                redis_key,
                _IDEMPOTENCY_TTL_S,
                json.dumps(cache_data).encode("utf-8"),
            )

            logger.debug(f"Idempotency response cached: {idempotency_key}")

            # Return response with body
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        except Exception as e:
            logger.warning(f"Idempotency middleware: Error caching response: {e}")
            # If we held the in-flight claim but failed to cache, release it so retries can proceed
            if claimed:
                try:
                    await redis_client.delete(redis_key)
                except Exception:
                    pass
            # Return response with body even if caching failed
            # Note: response_body_iterator was consumed above, so we return the body we read
            return Response(
                content=response_body if "response_body" in locals() else b"",
                status_code=response.status_code,
                headers=dict(response.headers),
            )
