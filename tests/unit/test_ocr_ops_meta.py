"""Path-to-10 W4: OCR provider meta endpoint honesty (no secrets)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.upstream.ai_status import get_ocr_providers_readiness
from src.main import app

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ocr" / "provider_status.json"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_ocr_providers_meta_not_configured(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)

    response = client.get("/api/v1/health/meta/ocr-providers")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "not_configured"
    assert data["providers"]["mistral"]["configured"] is False
    assert data["providers"]["gemini"]["configured"] is False
    assert data["providers"]["azure_di"]["configured"] is False
    assert data["providers"]["azure_di"]["enabled_in_prod"] is False
    assert "e4_non_goal" in data
    assert data["capabilities"]["ocr_artifacts_table"] is True
    assert data["capabilities"]["dispute_ack_stubs"] is True
    assert "as_of" in data
    assert data["endpoint"] == "/api/v1/health/meta/ocr-providers"
    assert "test-" not in json.dumps(data)


def test_ocr_providers_meta_mistral_only(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = client.get("/api/v1/health/meta/ocr-providers")
    data = response.json()

    assert data["status"] == "partial"
    assert data["providers"]["mistral"]["configured"] is True
    assert data["providers"]["gemini"]["configured"] is False
    assert "test-mistral-key" not in json.dumps(data)


def test_ocr_providers_meta_azure_di_partial(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://example.cognitiveservices.azure.com/")
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)

    data = get_ocr_providers_readiness()
    assert data["status"] == "partial"
    assert data["providers"]["azure_di"]["status"] == "partial"
    assert data["providers"]["azure_di"]["endpoint_present"] is True
    assert data["providers"]["azure_di"]["api_key_present"] is False
    assert "example.cognitiveservices" not in json.dumps(data)


def test_ocr_providers_meta_matches_fixture_shape(monkeypatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "fixture-mistral")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)

    fixture = json.loads(_FIXTURE.read_text())
    result = get_ocr_providers_readiness()

    assert result["status"] == fixture["status"]
    assert result["providers"]["mistral"]["configured"] == fixture["providers"]["mistral"]["configured"]
    assert result["providers"]["gemini"]["configured"] == fixture["providers"]["gemini"]["configured"]
    assert result["external_audit_import"]["ocr_configured"] == fixture["external_audit_import"]["ocr_configured"]


def test_readyz_includes_ocr_providers_summary(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "readyz-mistral")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "readyz-gemini")

    response = client.get("/api/v1/health/readyz")
    assert response.status_code in {200, 503}
    checks = response.json().get("checks", {})
    ocr = checks.get("ocr_providers", {})
    assert ocr.get("mistral_configured") is True
    assert ocr.get("gemini_configured") is True
    assert ocr.get("meta_endpoint") == "/api/v1/health/meta/ocr-providers"
    assert ocr.get("capabilities", {}).get("page_consensus_persist") is True
