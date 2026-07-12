"""Path-to-10 Preferred S10: Gemini review via catalog ``gemini_review`` breaker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domain.services.gemini_review_service import GeminiReviewService
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


def _service(*, api_key: str = "test-key") -> GeminiReviewService:
    svc = GeminiReviewService()
    svc.api_key = api_key
    return svc


def _mock_client(*, text: str = '{"scheme":"iso","findings":[],"score_breakdown":[]}') -> MagicMock:
    client = MagicMock()
    client.files.upload.return_value = MagicMock()
    response = MagicMock()
    response.text = text
    client.models.generate_content.return_value = response
    return client


@pytest.mark.asyncio
async def test_review_registers_preferred_gemini_review_breaker_on_success() -> None:
    svc = _service()
    client = _mock_client()

    with (
        patch("src.domain.services.gemini_review_service.USE_GOOGLE_GENAI", True),
        patch.object(svc, "_get_client", return_value=client),
    ):
        result = await svc.review(
            raw_pdf=b"%PDF-1.4 tiny",
            text="supplementary text for review",
            filename="audit.pdf",
        )

    assert result.provider_status == "completed"
    health = get_upstream_breaker("gemini_review").get_health()
    assert health["name"] == "gemini_review"
    assert health["state"] == CircuitState.CLOSED.value
    client.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_repeated_review_failures_open_gemini_review_circuit() -> None:
    svc = _service()
    client = MagicMock()
    client.files.upload.side_effect = RuntimeError("gemini unavailable")

    with (
        patch("src.domain.services.gemini_review_service.USE_GOOGLE_GENAI", True),
        patch.object(svc, "_get_client", return_value=client),
        patch("asyncio.sleep", return_value=None),
        patch("time.sleep", return_value=None),
    ):
        # failure_threshold=5; each review() retries twice → 3 reviews trip OPEN.
        for _ in range(3):
            result = await svc.review(raw_pdf=b"%PDF-1.4 tiny", text="x", filename="a.pdf")
            assert result.provider_status == "failed"

    assert get_upstream_breaker("gemini_review").state == CircuitState.OPEN

    with (
        patch("src.domain.services.gemini_review_service.USE_GOOGLE_GENAI", True),
        patch.object(svc, "_get_client", return_value=client),
    ):
        open_result = await svc.review(raw_pdf=b"%PDF-1.4 tiny", text="x", filename="a.pdf")

    assert open_result.provider_status == "failed"
    assert any("CircuitBreakerOpenError" in w for w in open_result.warnings)
    # Fail-fast once OPEN: no further outbound upload after the 5 failures that opened it.
    assert client.files.upload.call_count == 5


@pytest.mark.asyncio
async def test_review_does_not_invent_api_key_when_unconfigured() -> None:
    svc = _service(api_key="")
    with patch("src.domain.services.gemini_review_service.USE_GOOGLE_GENAI", True):
        result = await svc.review(raw_pdf=b"%PDF-1.4 tiny", text="x", filename="a.pdf")
    assert result.provider_status == "not_configured"
    assert "gemini_review" not in _circuit_registry


@pytest.mark.asyncio
async def test_open_circuit_raises_via_catalog_facade() -> None:
    cb = get_upstream_breaker("gemini_review")
    cb._state = CircuitState.OPEN
    cb._last_failure_time = 1e18

    from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

    async def _ok():
        return "should-not-run"

    with pytest.raises(CircuitBreakerOpenError) as exc:
        await call_via_upstream_breaker("gemini_review", _ok)
    assert exc.value.circuit_name == "gemini_review"
