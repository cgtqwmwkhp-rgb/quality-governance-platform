"""Wave D UAT polish — ACT-046 AI health auth, ACT-053 engineer dual gate docs."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.routes.ai_intelligence import ai_health_check
from src.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_ai_health_unauthenticated_returns_401_or_403(client: TestClient) -> None:
    response = client.get("/api/v1/ai/health")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_ai_health_redacts_secrets_and_requires_auth_flag(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)

    user = type("User", (), {"id": 1, "email": "ops@example.com"})()
    payload = await ai_health_check(current_user=user)  # type: ignore[arg-type]

    assert payload["auth_required"] is True
    assert payload["endpoint"] == "/api/v1/ai/health"
    assert payload["anthropic"]["api_key_present"] is True
    assert "sk-test-secret" not in str(payload)
    assert "services" not in payload
    assert payload["ocr_ai"]["status"] == "not_configured"


@pytest.mark.asyncio
async def test_ai_health_uses_upstream_readiness_not_theatre(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    user = type("User", (), {"id": 2, "email": "admin@example.com"})()
    with patch("src.infrastructure.upstream.ai_status.get_upstream_ai_readiness") as mock_ready:
        mock_ready.return_value = {"status": "configured", "mistral": {}, "gemini": {}}
        payload = await ai_health_check(current_user=user)  # type: ignore[arg-type]

    assert payload["status"] == "configured"
    assert payload["ocr_ai"]["status"] == "configured"
    mock_ready.assert_called_once()
