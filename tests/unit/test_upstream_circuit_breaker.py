"""Unit tests for Preferred S10 upstream circuit breaker foundation."""

from __future__ import annotations

import pytest

from src.domain.services.upstream_circuit_breaker import (
    UPSTREAM_BREAKER_NAMES,
    call_via_upstream_breaker,
    ensure_upstream_breakers_registered,
    get_upstream_breaker,
    get_upstream_breaker_health,
    is_upstream_degraded,
    list_upstream_breaker_health,
    upstream_degraded_summary,
)
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    _circuit_registry,
    _registry_lock,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    with _registry_lock:
        saved = dict(_circuit_registry)
        _circuit_registry.clear()
    yield
    with _registry_lock:
        _circuit_registry.clear()
        _circuit_registry.update(saved)


class TestCatalog:
    def test_canonical_names_cover_ocr_ai_blob(self) -> None:
        assert "mistral_analysis" in UPSTREAM_BREAKER_NAMES
        assert "gemini_ai" in UPSTREAM_BREAKER_NAMES
        assert "gemini_review" in UPSTREAM_BREAKER_NAMES
        assert "blob_storage" in UPSTREAM_BREAKER_NAMES
        assert "document_ai" in UPSTREAM_BREAKER_NAMES

    def test_unknown_name_rejected(self) -> None:
        with pytest.raises(KeyError, match="Unknown upstream breaker"):
            get_upstream_breaker("not-a-real-upstream")


class TestGetOrCreate:
    def test_creates_with_preferred_defaults(self) -> None:
        cb = get_upstream_breaker("mistral_analysis")
        assert cb.name == "mistral_analysis"
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 300.0
        assert cb.state == CircuitState.CLOSED

    def test_reuses_existing_registry_instance(self) -> None:
        prior = CircuitBreaker("gemini_ai", failure_threshold=2, recovery_timeout=9.0)
        got = get_upstream_breaker("gemini_ai")
        assert got is prior
        assert got.failure_threshold == 2

    def test_ensure_registers_all(self) -> None:
        breakers = ensure_upstream_breakers_registered()
        assert len(breakers) == len(UPSTREAM_BREAKER_NAMES)
        names = {cb.name for cb in breakers}
        assert names == set(UPSTREAM_BREAKER_NAMES)


class TestHealthAndDegraded:
    def test_list_unregistered_without_creating(self) -> None:
        rows = list_upstream_breaker_health(register_missing=False)
        assert len(rows) == len(UPSTREAM_BREAKER_NAMES)
        assert all(row["state"] == "unregistered" for row in rows)
        assert _circuit_registry == {}

    def test_list_registers_when_requested(self) -> None:
        rows = list_upstream_breaker_health(register_missing=True)
        assert all(row["state"] == "closed" for row in rows)
        assert set(_circuit_registry) == set(UPSTREAM_BREAKER_NAMES)

    def test_health_includes_role(self) -> None:
        health = get_upstream_breaker_health("blob_storage")
        assert health["role"] == "blob"
        assert health["name"] == "blob_storage"

    @pytest.mark.asyncio
    async def test_open_circuit_marks_degraded(self) -> None:
        cb = get_upstream_breaker("gemini_review")
        # Trip: failure_threshold is 5
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)

        summary = upstream_degraded_summary(register_missing=False)
        assert summary.degraded is True
        assert "gemini_review" in summary.open_circuits
        assert is_upstream_degraded(register_missing=False) is True
        assert "temporarily unavailable" in summary.message
        payload = summary.as_dict()
        assert payload["degraded"] is True
        assert "gemini_review" in payload["open_circuits"]

    def test_closed_summary_not_degraded(self) -> None:
        ensure_upstream_breakers_registered()
        summary = upstream_degraded_summary(register_missing=False)
        assert summary.degraded is False
        assert summary.open_circuits == ()
        assert "closed" in summary.message.lower()


class TestCallVia:
    @pytest.mark.asyncio
    async def test_call_success(self) -> None:
        result = await call_via_upstream_breaker("gemini_ai", _ok, 21)
        assert result == 42

    @pytest.mark.asyncio
    async def test_call_open_raises(self) -> None:
        cb = get_upstream_breaker("mistral_analysis")
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)

        with pytest.raises(CircuitBreakerOpenError):
            await call_via_upstream_breaker("mistral_analysis", _ok, 1)


async def _fail() -> None:
    raise RuntimeError("upstream failed")


def _ok(value: int) -> int:
    return value * 2
