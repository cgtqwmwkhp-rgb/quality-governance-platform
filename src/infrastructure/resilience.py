"""Resilience patterns: circuit breaker, timeouts, bulkhead."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1
    
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    last_failure_time: float = field(default=0.0, init=False)
    half_open_calls: int = field(default=0, init=False)
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return False
    
    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
        self.failure_count = 0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
    
    def get_health(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
        }


# Circuit breaker registry
_circuit_breaker_registry: dict[str, CircuitBreaker] = {}


def register_circuit_breaker(breaker: CircuitBreaker):
    """Register a circuit breaker in the global registry."""
    _circuit_breaker_registry[breaker.name] = breaker


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker by name from the registry."""
    return _circuit_breaker_registry.get(name)


def get_all_circuit_breaker_health() -> dict[str, dict]:
    """Get health status of all registered circuit breakers."""
    return {
        name: breaker.get_health()
        for name, breaker in _circuit_breaker_registry.items()
    }


# Universal circuit breaker decorator
def circuit_breaker(
    breaker: Optional[CircuitBreaker] = None,
    name: Optional[str] = None,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    half_open_max_calls: int = 1,
):
    """
    Decorator to add circuit breaker functionality to async functions.
    
    Usage:
        @circuit_breaker(name="my_service", failure_threshold=5)
        async def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        nonlocal breaker
        
        if breaker is None:
            breaker_name = name or func.__name__
            breaker = CircuitBreaker(
                name=breaker_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max_calls=half_open_max_calls,
            )
            register_circuit_breaker(breaker)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise RuntimeError(
                    f"Circuit breaker '{breaker.name}' is OPEN. "
                    f"Service unavailable."
                )
            
            if breaker.state == CircuitState.HALF_OPEN:
                breaker.half_open_calls += 1
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise RuntimeError(
                    f"Circuit breaker '{breaker.name}' is OPEN. "
                    f"Service unavailable."
                )
            
            if breaker.state == CircuitState.HALF_OPEN:
                breaker.half_open_calls += 1
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    # Handle both @circuit_breaker and @circuit_breaker(...) usage
    if callable(breaker) and name is None:
        # Used as @circuit_breaker without parentheses
        func = breaker
        breaker = None
        return decorator(func)
    
    return decorator


# Timeout decorator
def with_timeout(seconds: float):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"{func.__name__} timed out after {seconds}s")
        return wrapper
    return decorator


# Bulkhead (semaphore-based concurrency limiter)
class Bulkhead:
    def __init__(self, name: str, max_concurrent: int = 10):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        return self
    
    async def __aexit__(self, *args):
        self.semaphore.release()


# Pre-configured instances
DB_TIMEOUT = 5.0
REDIS_TIMEOUT = 2.0
EXTERNAL_API_TIMEOUT = 10.0

auth_bulkhead = Bulkhead("auth", max_concurrent=50)
business_bulkhead = Bulkhead("business", max_concurrent=100)
