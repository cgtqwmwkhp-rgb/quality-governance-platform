"""Login lockout store — Redis-backed with in-memory fallback (Path-to-10 S8).

Process-local dict lockout is insufficient for multi-instance App Service.
When ``REDIS_URL`` is set, failed-attempt timestamps live in a Redis sorted
set so lockouts are shared across workers. Redis errors fall back to memory.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 15 * 60  # 15 minutes
_REDIS_KEY_PREFIX = "qgp:login_lockout:"


class InMemoryLoginLockoutStore:
    """Process-local failed-attempt timestamps (dev / Redis-unavailable fallback)."""

    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = {}

    def _prune(self, email: str, now: float) -> list[float]:
        cutoff = now - LOCKOUT_DURATION_SECONDS
        recent = [t for t in self._attempts.get(email, []) if t > cutoff]
        self._attempts[email] = recent
        return recent

    async def check_lockout(self, email: str) -> int | None:
        """Return seconds until unlock if locked, else ``None``."""
        now = time.time()
        recent = self._prune(email, now)
        if len(recent) < MAX_FAILED_ATTEMPTS:
            return None
        unlock_in = int(max(recent) + LOCKOUT_DURATION_SECONDS - now)
        return max(unlock_in, 1)

    async def record_failure(self, email: str) -> None:
        now = time.time()
        self._prune(email, now)
        self._attempts.setdefault(email, []).append(now)

    async def clear(self, email: str) -> None:
        self._attempts.pop(email, None)


class RedisLoginLockoutStore:
    """Redis sorted-set lockout shared across app instances."""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None
        self._fallback = InMemoryLoginLockoutStore()

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(self._redis_url)
                await self._redis.ping()
            except Exception as exc:  # noqa: BLE001 — lockout must never break login
                logger.warning("Redis unavailable for login lockout, using in-memory: %s", exc)
                self._redis = None
        return self._redis

    def _key(self, email: str) -> str:
        return f"{_REDIS_KEY_PREFIX}{email}"

    async def check_lockout(self, email: str) -> int | None:
        client = await self._get_redis()
        if client is None:
            return await self._fallback.check_lockout(email)

        try:
            now = time.time()
            cutoff = now - LOCKOUT_DURATION_SECONDS
            key = self._key(email)
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zrange(key, -1, -1, withscores=True)
            results = await pipe.execute()
            count = int(results[1] or 0)
            if count < MAX_FAILED_ATTEMPTS:
                return None
            newest = results[2]
            most_recent = float(newest[0][1]) if newest else now
            unlock_in = int(most_recent + LOCKOUT_DURATION_SECONDS - now)
            return max(unlock_in, 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis lockout check failed, falling back to in-memory: %s", exc)
            return await self._fallback.check_lockout(email)

    async def record_failure(self, email: str) -> None:
        client = await self._get_redis()
        if client is None:
            await self._fallback.record_failure(email)
            return

        try:
            now = time.time()
            cutoff = now - LOCKOUT_DURATION_SECONDS
            key = self._key(email)
            member = f"{now}:{id(object())}"
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {member: now})
            pipe.expire(key, LOCKOUT_DURATION_SECONDS)
            await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis lockout record failed, falling back to in-memory: %s", exc)
            await self._fallback.record_failure(email)

    async def clear(self, email: str) -> None:
        client = await self._get_redis()
        if client is None:
            await self._fallback.clear(email)
            return

        try:
            await client.delete(self._key(email))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis lockout clear failed, falling back to in-memory: %s", exc)
            await self._fallback.clear(email)


_login_lockout_store: Optional[InMemoryLoginLockoutStore | RedisLoginLockoutStore] = None


def get_login_lockout_store() -> InMemoryLoginLockoutStore | RedisLoginLockoutStore:
    """Return the process-wide lockout store (Redis when configured)."""
    global _login_lockout_store
    if _login_lockout_store is None:
        redis_url = (os.getenv("REDIS_URL") or "").strip()
        if redis_url:
            _login_lockout_store = RedisLoginLockoutStore(redis_url)
        else:
            _login_lockout_store = InMemoryLoginLockoutStore()
    return _login_lockout_store


def reset_login_lockout_store_for_tests() -> None:
    """Clear the singleton — test helper only."""
    global _login_lockout_store
    _login_lockout_store = None


__all__ = [
    "MAX_FAILED_ATTEMPTS",
    "LOCKOUT_DURATION_SECONDS",
    "InMemoryLoginLockoutStore",
    "RedisLoginLockoutStore",
    "get_login_lockout_store",
    "reset_login_lockout_store_for_tests",
]
