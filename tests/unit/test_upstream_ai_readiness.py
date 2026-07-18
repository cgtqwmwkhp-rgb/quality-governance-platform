"""Path-to-10 S10: OCR/AI upstream readiness honesty."""

import os

from src.infrastructure.upstream.ai_status import (
    get_ocr_ops_capabilities,
    get_ocr_providers_readiness,
    get_upstream_ai_readiness,
)


def test_upstream_ai_not_configured_when_keys_missing(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = get_upstream_ai_readiness()
    assert result["status"] == "not_configured"
    assert result["mistral"]["api_key_present"] is False
    assert result["gemini"]["api_key_present"] is False
    assert "note" in result
    assert result["ocr_ping"]["status"] == "skipped"
    assert result["ocr_ping"]["connectivity"] == "unprobed"
    assert result["mistral"]["timeout_seconds"] == 120
    assert "circuits" in result
    # May already be registered if other unit tests imported AI services in-process.
    assert result["circuits"]["mistral_analysis"]["state"] in {
        "unregistered",
        "closed",
        "open",
        "half_open",
    }


def test_upstream_ai_partial_mistral_only(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = get_upstream_ai_readiness()
    assert result["status"] == "partial"
    assert result["mistral"]["status"] == "configured"
    assert result["gemini"]["status"] == "not_configured"
    assert result["mistral"]["ping"]["status"] == "skipped"


def test_upstream_ai_configured_both(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-gemini")
    result = get_upstream_ai_readiness()
    assert result["status"] == "configured"
    assert "note" not in result
    assert result["ocr_ping"]["connectivity"] == "unprobed"


def test_upstream_ai_honors_ocr_timeout_env(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("MISTRAL_OCR_TIMEOUT_SECONDS", "45")
    result = get_upstream_ai_readiness()
    assert result["mistral"]["timeout_seconds"] == 45
    # Never leak key material
    assert "test-mistral" not in str(result)
    assert os.getenv("MISTRAL_API_KEY") == "test-mistral"


def test_ocr_providers_readiness_includes_azure_di(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://di.example.azure.com/")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "azure-key-placeholder")

    result = get_ocr_providers_readiness()
    assert result["status"] == "partial"
    azure = result["providers"]["azure_di"]
    assert azure["configured"] is True
    assert azure["enabled_in_prod"] is False
    assert azure["used_in_library"] is False
    assert azure["used_in_prod"] is False
    assert azure["resource_scope"] == "qgp_dedicated_required"
    assert azure["jobsheet_resource_allowed"] is False
    assert "e4_non_goal" in result
    assert "azure-key-placeholder" not in str(result)
    assert "di.example.azure.com" not in str(result)


def test_ocr_providers_meta_azure_di_prod_flag_does_not_enable_in_meta(monkeypatch):
    """DS-1b: prod enable env must not flip enabled_in_prod on meta/readiness."""
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://di.example.azure.com/")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "azure-key")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD", "true")

    azure = get_ocr_providers_readiness()["providers"]["azure_di"]
    assert azure["prod_enable_flag_set"] is True
    assert azure["enabled_in_prod"] is False
    assert azure["used_in_prod"] is False


def test_ocr_providers_readiness_all_configured(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://di.example.azure.com/")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "azure-key")

    result = get_ocr_providers_readiness()
    assert result["status"] == "configured"
    assert result["providers"]["mistral"]["configured"] is True
    assert result["providers"]["gemini"]["configured"] is True
    assert result["providers"]["azure_di"]["configured"] is True
    assert result["capabilities"]["ocr_artifacts_table"]["status"] == "declared"
    assert result["capabilities"]["ocr_artifacts_table"]["database_available"] is None


def test_ocr_ops_capabilities_flags():
    caps = get_ocr_ops_capabilities()
    assert caps["ocr_artifacts_table"] == {
        "status": "declared",
        "schema_expected": True,
        "database_available": None,
        "probe": "not_run",
        "note": (
            "The application declares the ocr_artifacts schema, but this "
            "metadata endpoint does not probe the deployed database. "
            "database_available remains unknown until a database-backed "
            "OCR operation is exercised."
        ),
    }
    assert caps["page_consensus_persist"] is True
    assert caps["dispute_ack_stubs"] is True
    assert caps["provider_dial_on_probes"] is False
    assert "e4_non_goal" in caps


def test_settings_azure_di_defaults_off():
    from src.core.config import Settings

    settings = Settings()
    assert settings.azure_document_intelligence_endpoint == ""
    assert settings.azure_document_intelligence_key == ""
    assert settings.azure_document_intelligence_enable_prod is False
