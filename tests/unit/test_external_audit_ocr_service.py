"""Path-to-10 S1: OCR extraction collaborator for external audit import."""

from src.domain.services.external_audit_import_service import ExternalAuditImportService
from src.domain.services.external_audit_ocr_service import ExternalAuditOcrService


def test_merge_extractions_prefers_richer_ocr_corpus() -> None:
    text, pages, method = ExternalAuditOcrService._merge_extractions(
        native_text="one two three",
        native_pages=["one two three"],
        ocr_text="one two three four five six seven eight nine ten eleven",
        ocr_pages=["ocr"],
        native_method="pdf_text",
    )
    assert method == "mistral_ocr"
    assert text.startswith("one two three four")
    assert pages == ["ocr"]


def test_import_facade_reexports_ocr_merge_policy() -> None:
    args = dict(
        native_text="alpha beta",
        native_pages=["alpha beta"],
        ocr_text="",
        ocr_pages=[],
        native_method="docx",
    )
    assert ExternalAuditImportService._merge_extractions(**args) == ExternalAuditOcrService._merge_extractions(**args)
