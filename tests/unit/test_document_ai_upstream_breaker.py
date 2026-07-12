"""Path-to-10 Preferred S10: Document AI via catalog ``document_ai`` breaker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.document_ai_service import DocumentAIService
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


def _service(*, api_key: str = "test-key") -> DocumentAIService:
    svc = DocumentAIService()
    svc.api_key = api_key
    svc.base_url = "https://api.anthropic.test/v1"
    svc.model = "claude-test"
    return svc


@pytest.mark.asyncio
async def test_analyze_document_registers_preferred_document_ai_breaker_on_success() -> None:
    svc = _service()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "content": [
            {
                "text": (
                    '{"summary": "A policy summary.", "document_type": "policy", '
                    '"category": "governance", "tags": ["iso"], "keywords": ["quality"], '
                    '"topics": ["compliance"], "entities": {}, "sensitivity": "internal", '
                    '"confidence": 0.9, "has_tables": false, "has_images": false}'
                )
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await svc.analyze_document("Policy body text", "policy.pdf", "pdf")

    assert result.document_type == "policy"
    assert "policy summary" in result.summary.lower()
    health = get_upstream_breaker("document_ai").get_health()
    assert health["name"] == "document_ai"
    assert health["state"] == CircuitState.CLOSED.value


@pytest.mark.asyncio
async def test_repeated_analyze_failures_open_document_ai_circuit() -> None:
    svc = _service()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("anthropic unavailable"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        for _ in range(5):
            result = await svc.analyze_document("content", "doc.txt", "txt")
            # Failures fall back to local analysis (no invented provider success).
            assert result.confidence >= 0.0

    assert get_upstream_breaker("document_ai").state == CircuitState.OPEN

    with patch("httpx.AsyncClient", return_value=mock_client):
        open_result = await svc.analyze_document("content", "doc.txt", "txt")

    assert open_result.summary  # fallback still returned
    # Fail-fast: no further outbound call once OPEN.
    assert mock_client.post.await_count == 5


@pytest.mark.asyncio
async def test_analyze_document_does_not_invent_api_key_when_unconfigured() -> None:
    svc = _service(api_key="")
    result = await svc.analyze_document("content", "doc.txt", "txt")
    assert result.document_type in {"other", "policy", "procedure", "sop", "form", "manual", "guideline", "faq", "template", "record"}
    assert "document_ai" not in _circuit_registry


@pytest.mark.asyncio
async def test_extract_structured_actions_registers_and_fail_fasts() -> None:
    svc = _service()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("anthropic unavailable"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        for _ in range(5):
            rows, method, warnings = await svc.extract_structured_actions(
                "Reduce energy usage by installing LED lighting across sites.",
                "actions.txt",
            )
            assert method in {"ai_claude", "rule_based", "unknown"} or rows is not None
            assert isinstance(warnings, list)

    assert get_upstream_breaker("document_ai").state == CircuitState.OPEN

    with patch("httpx.AsyncClient", return_value=mock_client):
        await svc.extract_structured_actions("Reduce energy usage now.", "actions.txt")

    assert mock_client.post.await_count == 5


@pytest.mark.asyncio
async def test_open_circuit_raises_via_catalog_facade() -> None:
    cb = get_upstream_breaker("document_ai")
    cb._state = CircuitState.OPEN
    cb._last_failure_time = 1e18

    from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

    async def _ok():
        return "should-not-run"

    with pytest.raises(CircuitBreakerOpenError) as exc:
        await call_via_upstream_breaker("document_ai", _ok)
    assert exc.value.circuit_name == "document_ai"
