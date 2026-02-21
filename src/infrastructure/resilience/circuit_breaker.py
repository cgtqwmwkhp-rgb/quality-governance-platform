"""Circuit breaker pattern for external service calls with metrics tracking."""

import asyncio
import functools
import logging
import random
import threading
import time
from enum import Enum
from typing import Any, Callable, Sequence, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global circuit breaker registry
# ---------------------------------------------------------------------------

_registry_lock = threading.Lock()
_circuit_registry: dict[str, "CircuitBreaker"] = {}


def get_all_circuits() -> list["CircuitBreaker"]:
    with _registry_lock:
        return list(_circuit_registry.values())


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Async circuit breaker with configurable thresholds and metrics."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        # Metrics counters
        self._total_failures = 0
        self._transitions: list[dict[str, Any]] = []

        with _registry_lock:
            _circuit_registry[name] = self

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                logger.warning(f"Circuit breaker '{self.name}' is OPEN, rejecting call")
                raise CircuitBreakerOpenError(self.name)

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name)
                self._half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            old_state = self._state
            self._failure_count = 0
            self._half_open_calls = 0
            self._state = CircuitState.CLOSED
            if old_state != CircuitState.CLOSED:
                self._record_transition(old_state, CircuitState.CLOSED)
                logger.info(f"Circuit breaker '{self.name}' CLOSED (recovered)")

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                old_state = self._state
                self._state = CircuitState.OPEN
                if old_state != CircuitState.OPEN:
                    self._record_transition(old_state, CircuitState.OPEN)
                logger.error(f"Circuit breaker '{self.name}' OPENED after {self._failure_count} failures")

    def _record_transition(self, from_state: CircuitState, to_state: CircuitState) -> None:
        self._transitions.append(
            {
                "from": from_state.value,
                "to": to_state.value,
                "timestamp": time.time(),
            }
        )
        # Keep last 100 transitions
        if len(self._transitions) > 100:
            self._transitions = self._transitions[-100:]

    def get_health(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "total_failures": self._total_failures,
            "recent_transitions": self._transitions[-10:],
        }


class CircuitBreakerOpenError(Exception):
    def __init__(self, circuit_name: str):
        self.circuit_name = circuit_name
        super().__init__(f"Circuit breaker '{circuit_name}' is open")


# ---------------------------------------------------------------------------
# Retry with exponential backoff
# ---------------------------------------------------------------------------

DEFAULT_RETRYABLE: tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    retryable_exceptions: Sequence[Type[BaseException]] = DEFAULT_RETRYABLE,
):
    """Decorator that retries an async or sync function with exponential backoff + jitter.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Cap on computed delay.
        retryable_exceptions: Exception types that trigger a retry.
    """
    retryable = tuple(retryable_exceptions)

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except retryable as exc:
                        last_exc = exc
                        if attempt == max_retries:
                            break
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = random.uniform(0, delay * 0.5)
                        logger.warning(
                            "Retry %d/%d for %s after %.2fs (error: %s)",
                            attempt + 1,
                            max_retries,
                            func.__qualname__,
                            delay + jitter,
                            exc,
                        )
                        await asyncio.sleep(delay + jitter)
                raise last_exc  # type: ignore[misc]  # TYPE-IGNORE: MYPY-OVERRIDE

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except retryable as exc:
                        last_exc = exc
                        if attempt == max_retries:
                            break
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = random.uniform(0, delay * 0.5)
                        logger.warning(
                            "Retry %d/%d for %s after %.2fs (error: %s)",
                            attempt + 1,
                            max_retries,
                            func.__qualname__,
                            delay + jitter,
                            exc,
                        )
                        time.sleep(delay + jitter)
                raise last_exc  # type: ignore[misc]  # TYPE-IGNORE: MYPY-OVERRIDE

            return sync_wrapper

    return decorator
