"""Path-to-10 S1: stable operator-facing failure classification for import processing.

Canonical helpers for hard-AI detection and processing exception → reason-code
mapping. ``ExternalAuditImportService`` keeps thin compatibility wrappers.
"""

from __future__ import annotations


def is_hard_ai_failure(mistral_result: object, gemini_result: object) -> bool:
    """True when a configured AI provider failed and none completed successfully.

    ``not_configured`` / ``skipped`` are soft degradations so native-only
    heuristic analysis can still produce reviewable drafts.
    """
    mistral_status = str(getattr(mistral_result, "provider_status", "") or "")
    gemini_status = str(getattr(gemini_result, "provider_status", "") or "")
    if mistral_status == "completed" or gemini_status == "completed":
        return False
    return mistral_status == "failed" or gemini_status == "failed"


def classify_processing_failure(exc: BaseException) -> tuple[str, str]:
    """Map processing exceptions to stable operator-facing reason codes."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    combined = f"{name} {message}"
    if "ocr" in combined:
        return (
            "OCR_FAILED",
            "OCR processing failed before review could begin. Review logs and retry the job.",
        )
    if any(token in combined for token in ("mistral", "gemini", "ai_analysis", "consensus", "openai")):
        return (
            "AI_ANALYSIS_FAILED",
            "AI analysis failed before review could begin. Review logs and retry the job.",
        )
    if any(token in combined for token in ("queue", "celery", "broker", "kombu", "amqp")):
        return (
            "QUEUE_DISPATCH_FAILED",
            "Background queue dispatch failed during processing. Retry queueing or process synchronously.",
        )
    return (
        "IMPORT_PROCESSING_FAILED",
        "Import analysis failed before review could begin. Review logs and retry the job.",
    )


__all__ = [
    "is_hard_ai_failure",
    "classify_processing_failure",
]
