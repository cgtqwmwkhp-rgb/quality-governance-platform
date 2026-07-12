"""Path-to-10 Preferred S10: Mistral OCR via catalog ``mistral_analysis`` breaker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.mistral_ocr_service import MistralOCRService
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


def _service(*, api_key: str = "test-key") -> MistralOCRService:
    svc = MistralOCRService()
    svc.api_key = api_key
    svc.base_url = "https://api.mistral.test"
    svc.model = "mistral-ocr-latest"
    svc.timeout_seconds = 5
    return svc


@pytest.mark.asyncio
async def test_ocr_bytes_registers_preferred_mistral_breaker_on_success() -> None:
    svc = _service()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "pages": [
            {"markdown": "page one text"},
            {"text": "page two text"},
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await svc.ocr_bytes(b"%PDF-1.4", "scan.pdf", "application/pdf")

    assert result.provider_status == "completed"
    assert "page one text" in result.text
    health = get_upstream_breaker("mistral_analysis").get_health()
    assert health["name"] == "mistral_analysis"
    assert health["state"] == CircuitState.CLOSED.value


@pytest.mark.asyncio
async def test_repeated_ocr_failures_open_mistral_circuit() -> None:
    svc = _service()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("mistral ocr unavailable"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        for _ in range(5):
            result = await svc.ocr_bytes(b"img", "scan.png", "image/png")
            assert result.provider_status == "failed"

    assert get_upstream_breaker("mistral_analysis").state == CircuitState.OPEN

    with patch("httpx.AsyncClient", return_value=mock_client):
        open_result = await svc.ocr_bytes(b"img", "scan.png", "image/png")

    assert open_result.provider_status == "failed"
    assert open_result.note is not None
    assert "CircuitBreakerOpenError" in open_result.note
    # Fail-fast: no further outbound call once OPEN.
    assert mock_client.post.await_count == 5


@pytest.mark.asyncio
async def test_ocr_bytes_does_not_invent_api_key_when_unconfigured() -> None:
    svc = _service(api_key="")
    result = await svc.ocr_bytes(b"img", "scan.png", "image/png")
    assert result.provider_status == "not_configured"
    assert "mistral_analysis" not in _circuit_registry


@pytest.mark.asyncio
async def test_open_circuit_raises_via_catalog_facade() -> None:
    cb = get_upstream_breaker("mistral_analysis")
    cb._state = CircuitState.OPEN
    cb._last_failure_time = 1e18

    from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

    async def _ok():
        return "should-not-run"

    with pytest.raises(CircuitBreakerOpenError) as exc:
        await call_via_upstream_breaker("mistral_analysis", _ok)
    assert exc.value.circuit_name == "mistral_analysis"
