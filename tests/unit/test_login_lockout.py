"""Path-to-10 S8: Redis-backed login lockout with in-memory fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.security.login_lockout import (
    LOCKOUT_DURATION_SECONDS,
    MAX_FAILED_ATTEMPTS,
    InMemoryLoginLockoutStore,
    RedisLoginLockoutStore,
    get_login_lockout_store,
    reset_login_lockout_store_for_tests,
    resolve_lockout_duration_seconds,
    resolve_max_failed_attempts,
)


@pytest.fixture(autouse=True)
def _reset_lockout_singleton():
    reset_login_lockout_store_for_tests()
    yield
    reset_login_lockout_store_for_tests()


@pytest.mark.asyncio
async def test_in_memory_lockout_after_max_failures() -> None:
    store = InMemoryLoginLockoutStore()
    email = "ops@example.com"

    for _ in range(MAX_FAILED_ATTEMPTS - 1):
        await store.record_failure(email)
        assert await store.check_lockout(email) is None

    await store.record_failure(email)
    unlock_in = await store.check_lockout(email)
    assert unlock_in is not None
    assert 1 <= unlock_in <= LOCKOUT_DURATION_SECONDS

    await store.clear(email)
    assert await store.check_lockout(email) is None


@pytest.mark.asyncio
async def test_in_memory_failure_count_and_env_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_LOCKOUT_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("LOGIN_LOCKOUT_DURATION_SECONDS", "120")
    store = InMemoryLoginLockoutStore(
        max_failed_attempts=resolve_max_failed_attempts(),
        lockout_duration_seconds=resolve_lockout_duration_seconds(),
    )
    email = "tune@example.com"

    assert resolve_max_failed_attempts() == 3
    assert resolve_lockout_duration_seconds() == 120

    await store.record_failure(email)
    await store.record_failure(email)
    assert await store.failure_count(email) == 2
    assert await store.check_lockout(email) is None

    await store.record_failure(email)
    assert await store.failure_count(email) == 3
    unlock_in = await store.check_lockout(email)
    assert unlock_in is not None
    assert 1 <= unlock_in <= 120


def test_resolve_thresholds_reject_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_LOCKOUT_MAX_ATTEMPTS", "not-a-number")
    monkeypatch.setenv("LOGIN_LOCKOUT_DURATION_SECONDS", "0")
    assert resolve_max_failed_attempts() == MAX_FAILED_ATTEMPTS
    assert resolve_lockout_duration_seconds() == LOCKOUT_DURATION_SECONDS


@pytest.mark.asyncio
async def test_redis_store_falls_back_when_ping_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    store = RedisLoginLockoutStore("redis://example.invalid:6379/0")
    fake_mod = MagicMock()
    fake_mod.from_url.side_effect = ConnectionError("redis down")
    monkeypatch.setitem(__import__("sys").modules, "redis.asyncio", fake_mod)

    email = "fallback@example.com"
    for _ in range(MAX_FAILED_ATTEMPTS):
        await store.record_failure(email)
    unlock_in = await store.check_lockout(email)
    assert unlock_in is not None


@pytest.mark.asyncio
async def test_redis_store_uses_sorted_set_pipeline() -> None:
    store = RedisLoginLockoutStore("redis://localhost:6379/0")
    pipe = MagicMock()
    pipe.zremrangebyscore = MagicMock(return_value=pipe)
    pipe.zcard = MagicMock(return_value=pipe)
    pipe.zrange = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[0, MAX_FAILED_ATTEMPTS, [("m", 1_700_000_000.0)]])

    client = MagicMock()
    client.pipeline.return_value = pipe
    client.delete = AsyncMock(return_value=1)
    store._redis = client

    unlock_in = await store.check_lockout("locked@example.com")
    assert unlock_in is not None
    pipe.zremrangebyscore.assert_called()
    pipe.zcard.assert_called()

    pipe.execute = AsyncMock(return_value=[0, 1, None, MAX_FAILED_ATTEMPTS])
    await store.record_failure("locked@example.com")
    pipe.zadd.assert_called()

    await store.clear("locked@example.com")
    client.delete.assert_awaited()


def test_get_login_lockout_store_prefers_redis_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://cache.example:6379/0")
    reset_login_lockout_store_for_tests()
    store = get_login_lockout_store()
    assert isinstance(store, RedisLoginLockoutStore)


def test_get_login_lockout_store_memory_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_login_lockout_store_for_tests()
    store = get_login_lockout_store()
    assert isinstance(store, InMemoryLoginLockoutStore)
