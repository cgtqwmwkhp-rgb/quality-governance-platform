"""Path-to-10 S10: OCR/AI upstream readiness honesty."""

import os

from src.infrastructure.upstream.ai_status import get_upstream_ai_readiness


def test_upstream_ai_not_configured_when_keys_missing(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = get_upstream_ai_readiness()
    assert result["status"] == "not_configured"
    assert result["mistral"]["api_key_present"] is False
    assert result["gemini"]["api_key_present"] is False
    assert "note" in result


def test_upstream_ai_partial_mistral_only(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = get_upstream_ai_readiness()
    assert result["status"] == "partial"
    assert result["mistral"]["status"] == "configured"
    assert result["gemini"]["status"] == "not_configured"


def test_upstream_ai_configured_both(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-gemini")
    result = get_upstream_ai_readiness()
    assert result["status"] == "configured"
    assert "note" not in result
