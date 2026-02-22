"""Tests for resilience patterns."""
import asyncio
import importlib.util
import time
from pathlib import Path

import pytest

# The standalone resilience.py is shadowed by the resilience/ package.
# Load CircuitBreaker, Bulkhead, with_timeout, get_all_circuit_breaker_health from the file.
_standalone = Path(__file__).resolve().parents[2] / "src" / "infrastructure" / "resilience.py"
_spec = importlib.util.spec_from_file_location("_resilience_standalone", str(_standalone))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CircuitBreaker = _mod.CircuitBreaker
CircuitState = _mod.CircuitState
Bulkhead = _mod.Bulkhead
with_timeout = _mod.with_timeout
get_all_circuit_breaker_health = _mod.get_all_circuit_breaker_health


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(name="test_open", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_recovers_after_timeout(self):
        cb = CircuitBreaker(
            name="test_recover", failure_threshold=2, recovery_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_closes_half_open(self):
        cb = CircuitBreaker(
            name="test_close", failure_threshold=1, recovery_timeout=0.01
        )
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_health_report(self):
        cb = CircuitBreaker(name="test_health")
        health = cb.get_health()
        assert health["name"] == "test_health"
        assert health["state"] == "closed"


class TestBulkhead:
    @pytest.mark.asyncio
    async def test_limits_concurrency(self):
        bh = Bulkhead("test_bh", max_concurrent=2)
        results = []

        async def task(n):
            async with bh:
                results.append(n)
                await asyncio.sleep(0.01)

        await asyncio.gather(task(1), task(2), task(3))
        assert len(results) == 3


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        @with_timeout(0.01)
        async def slow_func():
            await asyncio.sleep(1)

        with pytest.raises(TimeoutError):
            await slow_func()

    @pytest.mark.asyncio
    async def test_fast_func_succeeds(self):
        @with_timeout(1.0)
        async def fast_func():
            return 42

        assert await fast_func() == 42
