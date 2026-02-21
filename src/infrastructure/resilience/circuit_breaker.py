"""Circuit breaker pattern for external service calls."""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Async circuit breaker with configurable thresholds."""

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
            self._failure_count = 0
            self._half_open_calls = 0
            if self._state != CircuitState.CLOSED:
                logger.info(f"Circuit breaker '{self.name}' CLOSED (recovered)")
            self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(f"Circuit breaker '{self.name}' OPENED after {self._failure_count} failures")

    def get_health(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
        }


class CircuitBreakerOpenError(Exception):
    def __init__(self, circuit_name: str):
        self.circuit_name = circuit_name
        super().__init__(f"Circuit breaker '{circuit_name}' is open")
