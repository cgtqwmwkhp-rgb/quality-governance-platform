"""Unit tests for CircuitBreaker, CircuitBreakerOpenError, and retry_with_backoff.

Tests state transitions, call routing, metrics, and the retry decorator.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    _circuit_registry,
    _registry_lock,
    get_all_circuits,
    retry_with_backoff,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset circuit registry between tests."""
    with _registry_lock:
        saved = dict(_circuit_registry)
        _circuit_registry.clear()
    yield
    with _registry_lock:
        _circuit_registry.clear()
        _circuit_registry.update(saved)


# =========================================================================
# CircuitState enum
# =========================================================================


class TestCircuitState:
    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"


# =========================================================================
# CircuitBreakerOpenError
# =========================================================================


class TestCircuitBreakerOpenError:
    def test_stores_circuit_name(self):
        err = CircuitBreakerOpenError("my-service")
        assert err.circuit_name == "my-service"

    def test_message(self):
        err = CircuitBreakerOpenError("redis")
        assert "redis" in str(err)
        assert "open" in str(err)


# =========================================================================
# CircuitBreaker — initialization
# =========================================================================


class TestCircuitBreakerInit:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test-init", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_default_thresholds(self):
        cb = CircuitBreaker("test-defaults")
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.half_open_max_calls == 1

    def test_registered_in_global_registry(self):
        cb = CircuitBreaker("test-registry")
        circuits = get_all_circuits()
        assert any(c.name == "test-registry" for c in circuits)

    def test_custom_thresholds(self):
        cb = CircuitBreaker("custom", failure_threshold=2, recovery_timeout=10.0, half_open_max_calls=3)
        assert cb.failure_threshold == 2
        assert cb.recovery_timeout == 10.0
        assert cb.half_open_max_calls == 3


# =========================================================================
# CircuitBreaker — state property
# =========================================================================


class TestCircuitBreakerStateProperty:
    def test_closed_state_returned(self):
        cb = CircuitBreaker("sp-closed")
        assert cb.state == CircuitState.CLOSED

    def test_open_state_returned_within_timeout(self):
        cb = CircuitBreaker("sp-open", recovery_timeout=60)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.monotonic()
        assert cb.state == CircuitState.OPEN

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("sp-half", recovery_timeout=0.01)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.monotonic() - 1
        assert cb.state == CircuitState.HALF_OPEN


# =========================================================================
# CircuitBreaker — call method
# =========================================================================


class TestCircuitBreakerCall:
    @pytest.mark.asyncio
    async def test_successful_async_call(self):
        cb = CircuitBreaker("call-ok")
        func = AsyncMock(return_value="result")
        result = await cb.call(func, "arg1")
        assert result == "result"
        func.assert_awaited_once_with("arg1")

    @pytest.mark.asyncio
    async def test_successful_sync_call(self):
        cb = CircuitBreaker("call-sync")
        func = MagicMock(return_value=42)
        result = await cb.call(func, 1, 2)
        assert result == 42
        func.assert_called_once_with(1, 2)

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_call(self):
        cb = CircuitBreaker("call-open", recovery_timeout=60)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.monotonic()

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(AsyncMock())

    @pytest.mark.asyncio
    async def test_failure_increments_count(self):
        cb = CircuitBreaker("call-fail", failure_threshold=10)
        func = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            await cb.call(func)

        assert cb._failure_count == 1
        assert cb._total_failures == 1

    @pytest.mark.asyncio
    @patch("src.infrastructure.resilience.circuit_breaker.CircuitBreaker._emit_transition_metric")
    async def test_threshold_breached_opens_circuit(self, mock_metric):
        cb = CircuitBreaker("call-threshold", failure_threshold=2)
        func = AsyncMock(side_effect=RuntimeError("boom"))

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(func)

        assert cb._state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_limits_calls(self):
        cb = CircuitBreaker("call-half-limit", failure_threshold=2, recovery_timeout=0.01, half_open_max_calls=1)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.monotonic() - 1

        func = AsyncMock(return_value="ok")
        result = await cb.call(func)
        assert result == "ok"

        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.monotonic() - 1
        cb._half_open_calls = 1

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(func)


# =========================================================================
# CircuitBreaker — success/failure handlers
# =========================================================================


class TestOnSuccess:
    @pytest.mark.asyncio
    @patch("src.infrastructure.resilience.circuit_breaker.CircuitBreaker._emit_transition_metric")
    async def test_resets_failure_count(self, mock_metric):
        cb = CircuitBreaker("success-reset", failure_threshold=5)
        cb._failure_count = 3
        cb._state = CircuitState.HALF_OPEN
        await cb._on_success()
        assert cb._failure_count == 0
        assert cb._state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_already_closed_no_transition_recorded(self):
        cb = CircuitBreaker("success-noop")
        cb._state = CircuitState.CLOSED
        await cb._on_success()
        assert len(cb._transitions) == 0


class TestOnFailure:
    @pytest.mark.asyncio
    @patch("src.infrastructure.resilience.circuit_breaker.CircuitBreaker._emit_transition_metric")
    async def test_increments_failure_count(self, mock_metric):
        cb = CircuitBreaker("fail-inc", failure_threshold=10)
        await cb._on_failure()
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    @patch("src.infrastructure.resilience.circuit_breaker.CircuitBreaker._emit_transition_metric")
    async def test_opens_when_threshold_reached(self, mock_metric):
        cb = CircuitBreaker("fail-open", failure_threshold=3)
        for _ in range(3):
            await cb._on_failure()
        assert cb._state == CircuitState.OPEN


# =========================================================================
# CircuitBreaker — reset and health
# =========================================================================


class TestReset:
    @pytest.mark.asyncio
    @patch("src.infrastructure.resilience.circuit_breaker.CircuitBreaker._emit_transition_metric")
    async def test_resets_to_closed(self, mock_metric):
        cb = CircuitBreaker("reset-test", failure_threshold=2)
        cb._state = CircuitState.OPEN
        cb._failure_count = 5
        cb._half_open_calls = 1

        await cb.reset()
        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._half_open_calls == 0

    @pytest.mark.asyncio
    async def test_reset_when_already_closed_is_noop(self):
        cb = CircuitBreaker("reset-noop")
        await cb.reset()
        assert cb._state == CircuitState.CLOSED


class TestGetHealth:
    def test_health_dict_keys(self):
        cb = CircuitBreaker("health-test")
        health = cb.get_health()
        assert "name" in health
        assert "state" in health
        assert "failure_count" in health
        assert "failure_threshold" in health
        assert "total_failures" in health
        assert "recent_transitions" in health

    def test_health_state_value(self):
        cb = CircuitBreaker("health-state")
        assert cb.get_health()["state"] == "closed"


# =========================================================================
# Transition recording
# =========================================================================


class TestRecordTransition:
    def test_records_transition(self):
        cb = CircuitBreaker("trans-record")
        with patch.object(cb, "_emit_transition_metric"):
            cb._record_transition(CircuitState.CLOSED, CircuitState.OPEN)
        assert len(cb._transitions) == 1
        assert cb._transitions[0]["from"] == "closed"
        assert cb._transitions[0]["to"] == "open"

    def test_caps_at_100_transitions(self):
        cb = CircuitBreaker("trans-cap")
        with patch.object(cb, "_emit_transition_metric"):
            for _ in range(150):
                cb._record_transition(CircuitState.CLOSED, CircuitState.OPEN)
        assert len(cb._transitions) <= 100


# =========================================================================
# retry_with_backoff decorator
# =========================================================================


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        @retry_with_backoff(max_retries=3, base_delay=0.001)
        async def good_func():
            return "ok"

        assert await good_func() == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.001)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "recovered"

        result = await flaky_func()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        @retry_with_backoff(max_retries=1, base_delay=0.001)
        async def always_fail():
            raise TimeoutError("gone")

        with pytest.raises(TimeoutError):
            await always_fail()

    @pytest.mark.asyncio
    async def test_non_retryable_exception_not_retried(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.001)
        async def bad_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await bad_func()
        assert call_count == 1

    def test_sync_function_retries(self):
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.001)
        def flaky_sync():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("fail")
            return "ok"

        assert flaky_sync() == "ok"
        assert call_count == 2

    def test_sync_raises_after_max_retries(self):
        @retry_with_backoff(max_retries=1, base_delay=0.001)
        def always_fail():
            raise OSError("nope")

        with pytest.raises(OSError):
            always_fail()

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.001, retryable_exceptions=[ValueError])
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("retryable now")
            return "done"

        result = await func()
        assert result == "done"
        assert call_count == 3


# =========================================================================
# Global registry
# =========================================================================


class TestGetAllCircuits:
    def test_returns_registered_circuits(self):
        cb1 = CircuitBreaker("reg-1")
        cb2 = CircuitBreaker("reg-2")
        circuits = get_all_circuits()
        names = {c.name for c in circuits}
        assert "reg-1" in names
        assert "reg-2" in names

    def test_returns_copy_not_reference(self):
        CircuitBreaker("reg-copy")
        c1 = get_all_circuits()
        c2 = get_all_circuits()
        assert c1 is not c2
