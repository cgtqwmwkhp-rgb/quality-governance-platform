"""
Idempotency Middleware for FastAPI

Features:
- Intercepts POST requests with Idempotency-Key header
- Caches responses in Redis with 24h TTL
- Detects payload mismatches and returns 409 conflict
- Gracefully falls back if Redis is unavailable
"""

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


def _make_key(idempotency_key: str) -> str:
    """Create Redis key with prefix."""
    return f"idem:{idempotency_key}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle idempotency keys for POST requests.

    Intercepts POST requests with Idempotency-Key header:
    - Checks Redis for existing cached response
    - If found and payload hash matches, returns cached response
    - If found but payload hash differs, returns 409 Conflict
    - If not found, executes request and caches response with 24h TTL
    - Skips non-POST requests
    - Falls back gracefully if Redis is unavailable
    """

    async def dispatch(self, request: Request, call_next):
        # Skip non-POST requests
        if request.method != "POST":
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

        # Check Redis for existing key
        redis_key = _make_key(idempotency_key)
        try:
            cached_data = await redis_client.get(redis_key)
            if cached_data:
                # Parse cached response data (Redis may return bytes)
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode("utf-8")
                cached_response = json.loads(cached_data)

                # Check if payload hash matches
                cached_hash = cached_response.get("payload_hash")
                if cached_hash != payload_hash:
                    # Payload mismatch - return 409 Conflict
                    logger.warning(
                        f"Idempotency key conflict: {idempotency_key}",
                        extra={"idempotency_key": idempotency_key},
                    )
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "Idempotency key conflict: request payload differs from original request",
                            "error_code": "IDEMPOTENCY_CONFLICT",
                        },
                    )

                # Return cached response
                logger.debug(f"Idempotency cache hit: {idempotency_key}")

                # Handle body encoding (may be base64 if original was binary)
                body_content = cached_response["body"]
                if cached_response["headers"].get("X-Idempotency-Body-Encoding") == "base64":
                    import base64

                    body_content = base64.b64decode(body_content)
                    # Remove the encoding header from response
                    response_headers = {
                        k: v for k, v in cached_response["headers"].items() if k != "X-Idempotency-Body-Encoding"
                    }
                else:
                    response_headers = cached_response["headers"]
                    body_content = body_content.encode("utf-8") if isinstance(body_content, str) else body_content

                response = Response(
                    content=body_content,
                    status_code=cached_response["status_code"],
                    headers=response_headers,
                )
                return response

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
                # If it's binary, encode as base64 or store as-is
                import base64

                body_str = base64.b64encode(response_body).decode("utf-8")
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
                86400,  # 24 hours
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
            # Return response with body even if caching failed
            # Note: response_body_iterator was consumed above, so we return the body we read
            return Response(
                content=response_body if "response_body" in locals() else b"",
                status_code=response.status_code,
                headers=dict(response.headers),
            )
