"""Path-to-10 Preferred S10: Gemini AI via catalog ``gemini_ai`` breaker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domain.services.gemini_ai_service import GeminiAIService
from src.domain.services.upstream_circuit_breaker import get_upstream_breaker
from src.infrastructure.resilience.circuit_breaker import (
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


def _service(*, api_key: str = "test-key") -> GeminiAIService:
    svc = GeminiAIService()
    svc.api_key = api_key
    return svc


def _mock_client(*, text: str = '[{"id":"section-1","title":"T","description":"d","questions":[]}]') -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.text = text
    client.models.generate_content.return_value = response
    return client


@pytest.mark.asyncio
async def test_prompt_to_template_registers_preferred_gemini_ai_breaker_on_success() -> None:
    svc = _service()
    client = _mock_client()

    with (
        patch("src.domain.services.gemini_ai_service.USE_GOOGLE_GENAI", True),
        patch.object(svc, "_get_client", return_value=client),
    ):
        sections = await svc.prompt_to_template("Build a short ISO audit template")

    assert isinstance(sections, list)
    assert sections[0]["id"] == "section-1"
    health = get_upstream_breaker("gemini_ai").get_health()
    assert health["name"] == "gemini_ai"
    assert health["state"] == CircuitState.CLOSED.value
    client.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_repeated_prompt_failures_open_gemini_ai_circuit() -> None:
    svc = _service()
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("gemini unavailable")

    with (
        patch("src.domain.services.gemini_ai_service.USE_GOOGLE_GENAI", True),
        patch.object(svc, "_get_client", return_value=client),
        patch("asyncio.sleep", return_value=None),
        patch("time.sleep", return_value=None),
    ):
        # failure_threshold=5; each prompt_to_template retries 3×.
        # Call 1 records 3 failures; call 2 opens mid-retry (5th failure) then fail-fasts.
        with pytest.raises(RuntimeError):
            await svc.prompt_to_template("x")
        with pytest.raises((RuntimeError, CircuitBreakerOpenError)):
            await svc.prompt_to_template("x")

    assert get_upstream_breaker("gemini_ai").state == CircuitState.OPEN

    with (
        patch("src.domain.services.gemini_ai_service.USE_GOOGLE_GENAI", True),
        patch.object(svc, "_get_client", return_value=client),
    ):
        with pytest.raises(CircuitBreakerOpenError) as exc:
            await svc.prompt_to_template("x")

    assert exc.value.circuit_name == "gemini_ai"
    # Fail-fast once OPEN: no further outbound generate after the 5 failures that opened it.
    assert client.models.generate_content.call_count == 5


@pytest.mark.asyncio
async def test_prompt_to_template_does_not_invent_api_key_when_unconfigured() -> None:
    svc = _service(api_key="")
    with patch("src.domain.services.gemini_ai_service.USE_GOOGLE_GENAI", True):
        with pytest.raises(RuntimeError, match="unavailable"):
            await svc.prompt_to_template("x")
    assert "gemini_ai" not in _circuit_registry


@pytest.mark.asyncio
async def test_open_circuit_raises_via_catalog_facade() -> None:
    cb = get_upstream_breaker("gemini_ai")
    cb._state = CircuitState.OPEN
    cb._last_failure_time = 1e18

    from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

    async def _ok():
        return "should-not-run"

    with pytest.raises(CircuitBreakerOpenError) as exc:
        await call_via_upstream_breaker("gemini_ai", _ok)
    assert exc.value.circuit_name == "gemini_ai"
