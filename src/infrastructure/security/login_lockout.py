"""Login lockout store — Redis-backed with in-memory fallback (Path-to-10 S8).

Process-local dict lockout is insufficient for multi-instance App Service.
When ``REDIS_URL`` is set, failed-attempt timestamps live in a Redis sorted
set so lockouts are shared across workers. Redis errors fall back to memory.

Thresholds are env-overridable (``LOGIN_LOCKOUT_MAX_ATTEMPTS``,
``LOGIN_LOCKOUT_DURATION_SECONDS``) so operators can tune without code edits.
Defaults remain 5 attempts / 15 minutes.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_FAILED_ATTEMPTS = 5
_DEFAULT_LOCKOUT_DURATION_SECONDS = 15 * 60  # 15 minutes
_REDIS_KEY_PREFIX = "qgp:login_lockout:"


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r — using default %s", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%s below minimum %s — using default %s", name, value, minimum, default)
        return default
    return value


def resolve_max_failed_attempts() -> int:
    """Max failed logins before lockout (env ``LOGIN_LOCKOUT_MAX_ATTEMPTS``)."""
    return _env_int("LOGIN_LOCKOUT_MAX_ATTEMPTS", _DEFAULT_MAX_FAILED_ATTEMPTS, minimum=1)


def resolve_lockout_duration_seconds() -> int:
    """Lockout window seconds (env ``LOGIN_LOCKOUT_DURATION_SECONDS``)."""
    return _env_int(
        "LOGIN_LOCKOUT_DURATION_SECONDS",
        _DEFAULT_LOCKOUT_DURATION_SECONDS,
        minimum=1,
    )


# Module-level defaults for importers / tests (resolved at import; re-read in helpers).
MAX_FAILED_ATTEMPTS = _DEFAULT_MAX_FAILED_ATTEMPTS
LOCKOUT_DURATION_SECONDS = _DEFAULT_LOCKOUT_DURATION_SECONDS


class InMemoryLoginLockoutStore:
    """Process-local failed-attempt timestamps (dev / Redis-unavailable fallback)."""

    def __init__(
        self,
        *,
        max_failed_attempts: int | None = None,
        lockout_duration_seconds: int | None = None,
    ) -> None:
        self._attempts: dict[str, list[float]] = {}
        self._max_failed_attempts = (
            max_failed_attempts if max_failed_attempts is not None else resolve_max_failed_attempts()
        )
        self._lockout_duration_seconds = (
            lockout_duration_seconds if lockout_duration_seconds is not None else resolve_lockout_duration_seconds()
        )

    def _prune(self, email: str, now: float) -> list[float]:
        cutoff = now - self._lockout_duration_seconds
        recent = [t for t in self._attempts.get(email, []) if t > cutoff]
        self._attempts[email] = recent
        return recent

    async def failure_count(self, email: str) -> int:
        """Return recent failure count within the lockout window."""
        return len(self._prune(email, time.time()))

    async def check_lockout(self, email: str) -> int | None:
        """Return seconds until unlock if locked, else ``None``."""
        now = time.time()
        recent = self._prune(email, now)
        if len(recent) < self._max_failed_attempts:
            return None
        unlock_in = int(max(recent) + self._lockout_duration_seconds - now)
        return max(unlock_in, 1)

    async def record_failure(self, email: str) -> None:
        now = time.time()
        recent = self._prune(email, now)
        recent.append(now)
        self._attempts[email] = recent
        if len(recent) >= self._max_failed_attempts:
            logger.info(
                "login_lockout_engaged backend=memory email_hash=%s failures=%s duration_s=%s",
                hash(email.lower()),
                len(recent),
                self._lockout_duration_seconds,
            )

    async def clear(self, email: str) -> None:
        self._attempts.pop(email, None)


class RedisLoginLockoutStore:
    """Redis sorted-set lockout shared across app instances."""

    def __init__(
        self,
        redis_url: str,
        *,
        max_failed_attempts: int | None = None,
        lockout_duration_seconds: int | None = None,
    ):
        self._redis_url = redis_url
        self._redis = None
        self._max_failed_attempts = (
            max_failed_attempts if max_failed_attempts is not None else resolve_max_failed_attempts()
        )
        self._lockout_duration_seconds = (
            lockout_duration_seconds if lockout_duration_seconds is not None else resolve_lockout_duration_seconds()
        )
        self._fallback = InMemoryLoginLockoutStore(
            max_failed_attempts=self._max_failed_attempts,
            lockout_duration_seconds=self._lockout_duration_seconds,
        )

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

    async def failure_count(self, email: str) -> int:
        client = await self._get_redis()
        if client is None:
            return await self._fallback.failure_count(email)

        try:
            now = time.time()
            cutoff = now - self._lockout_duration_seconds
            key = self._key(email)
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            results = await pipe.execute()
            return int(results[1] or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis lockout failure_count failed, falling back to in-memory: %s", exc)
            return await self._fallback.failure_count(email)

    async def check_lockout(self, email: str) -> int | None:
        client = await self._get_redis()
        if client is None:
            return await self._fallback.check_lockout(email)

        try:
            now = time.time()
            cutoff = now - self._lockout_duration_seconds
            key = self._key(email)
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zrange(key, -1, -1, withscores=True)
            results = await pipe.execute()
            count = int(results[1] or 0)
            if count < self._max_failed_attempts:
                return None
            newest = results[2]
            most_recent = float(newest[0][1]) if newest else now
            unlock_in = int(most_recent + self._lockout_duration_seconds - now)
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
            cutoff = now - self._lockout_duration_seconds
            key = self._key(email)
            member = f"{now}:{id(object())}"
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {member: now})
            pipe.expire(key, self._lockout_duration_seconds)
            pipe.zcard(key)
            results = await pipe.execute()
            count = int(results[3] or 0)
            if count >= self._max_failed_attempts:
                logger.info(
                    "login_lockout_engaged backend=redis email_hash=%s failures=%s duration_s=%s",
                    hash(email.lower()),
                    count,
                    self._lockout_duration_seconds,
                )
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
    "resolve_max_failed_attempts",
    "resolve_lockout_duration_seconds",
]
