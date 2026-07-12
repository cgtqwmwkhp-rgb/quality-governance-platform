"""Path-to-10 S1: external_audit_import_failure classification helpers."""

from types import SimpleNamespace

from src.domain.services.external_audit_import_failure import classify_processing_failure, is_hard_ai_failure
from src.domain.services.external_audit_import_service import ExternalAuditImportService


def test_classify_processing_failure_reason_codes() -> None:
    assert classify_processing_failure(RuntimeError("OCR timeout"))[0] == "OCR_FAILED"
    assert classify_processing_failure(RuntimeError("mistral chat failed"))[0] == "AI_ANALYSIS_FAILED"
    assert classify_processing_failure(ConnectionError("celery broker down"))[0] == "QUEUE_DISPATCH_FAILED"
    assert classify_processing_failure(RuntimeError("unexpected boom"))[0] == "IMPORT_PROCESSING_FAILED"


def test_is_hard_ai_failure_only_when_configured_provider_fails() -> None:
    completed = SimpleNamespace(provider_status="completed")
    failed = SimpleNamespace(provider_status="failed")
    not_configured = SimpleNamespace(provider_status="not_configured")
    skipped = SimpleNamespace(provider_status="skipped")

    assert is_hard_ai_failure(failed, failed) is True
    assert is_hard_ai_failure(failed, not_configured) is True
    assert is_hard_ai_failure(failed, completed) is False
    assert is_hard_ai_failure(not_configured, skipped) is False
    assert is_hard_ai_failure(not_configured, not_configured) is False


def test_import_service_facade_delegates_to_failure_helpers() -> None:
    exc = RuntimeError("OCR timeout")
    assert ExternalAuditImportService._classify_processing_failure(exc) == classify_processing_failure(exc)

    failed = SimpleNamespace(provider_status="failed")
    skipped = SimpleNamespace(provider_status="skipped")
    assert ExternalAuditImportService._is_hard_ai_failure(failed, skipped) is is_hard_ai_failure(failed, skipped)
