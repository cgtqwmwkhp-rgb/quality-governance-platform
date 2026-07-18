"""Golden-corpus CER gate for library document intelligence merge policy."""

from __future__ import annotations

import json
from pathlib import Path

from src.domain.services.external_audit_ocr_service import ExternalAuditOcrService
from src.domain.services.ocr_consensus import character_error_rate

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ocr" / "library_golden_corpus.json"


def test_library_golden_corpus_merge_meets_cer_gate() -> None:
    fixture = json.loads(_FIXTURE.read_text())
    text, _pages, method = ExternalAuditOcrService._merge_extractions(
        native_text=fixture["native_text"],
        native_pages=[fixture["native_text"]],
        ocr_text=fixture["ocr_text"],
        ocr_pages=[fixture["ocr_text"]],
        native_method="pdf_text",
    )
    cer = character_error_rate(fixture["reference_text"], text)
    assert cer is not None
    assert cer <= fixture["max_character_error_rate"]
    assert method.startswith("mistral")
