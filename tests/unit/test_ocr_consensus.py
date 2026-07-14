"""Unit coverage for the credential-free OCR consensus scaffold."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.domain.services.ocr_consensus import (
    OCRPageCandidate,
    build_page_consensus,
    character_error_rate,
)
from src.infrastructure.external.azure_document_intelligence import AzureDocumentIntelligenceClient

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "ocr" / "page_consensus.json"


def test_page_consensus_matches_golden_fixture() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    candidates = [OCRPageCandidate(**candidate) for candidate in fixture["candidates"]]

    result = build_page_consensus(candidates, reference_text=fixture["reference_text"])

    assert result.page_number == 1
    assert result.selected_provider == "azure_document_intelligence"
    assert result.selected_text == fixture["reference_text"]
    assert result.agreement == 1.0
    assert result.character_error_rate == 0.0


def test_character_error_rate_tracks_character_substitutions() -> None:
    assert character_error_rate("audit", "adit") == 0.2
    assert character_error_rate("", "audit") is None


def test_page_consensus_requires_candidates_from_one_page() -> None:
    candidates = [
        OCRPageCandidate(provider="first", page_number=1, text="one"),
        OCRPageCandidate(provider="second", page_number=2, text="two"),
    ]

    with pytest.raises(ValueError, match="same page"):
        build_page_consensus(candidates)


@pytest.mark.asyncio
async def test_azure_document_intelligence_is_credential_free_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)
    client = AzureDocumentIntelligenceClient()

    result = await client.analyze_document(b"document", "audit.pdf", "application/pdf")

    assert not client.is_configured
    assert result.provider_status == "not_configured"
    assert result.pages == []


@pytest.mark.asyncio
async def test_azure_document_intelligence_does_not_enable_network_calls() -> None:
    client = AzureDocumentIntelligenceClient(endpoint="https://example.azure.com", api_key="test-key")

    result = await client.analyze_document(b"document", "audit.pdf", "application/pdf")

    assert client.is_configured
    assert result.provider_status == "stub_not_enabled"
    assert "not enabled" in (result.note or "")
