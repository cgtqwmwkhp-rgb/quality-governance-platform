"""Re-export from canonical domain service.

The single source of truth for external audit import orchestration lives in
``src.domain.services.external_audit_import_service`` (thin facade over OCR,
analysis, and promotion collaborators after Preferred S1 split). This module is
the Path-to-10 S1 dual-service thin re-export so callers using ``src.services``
keep working.
"""

from src.domain.services.external_audit_import_service import (
    MAX_SOURCE_FILE_BYTES,
    PROCESSING_TTL_SECONDS,
    ExternalAuditImportService,
    PromotionResult,
)

__all__ = [
    "MAX_SOURCE_FILE_BYTES",
    "PROCESSING_TTL_SECONDS",
    "PromotionResult",
    "ExternalAuditImportService",
]
