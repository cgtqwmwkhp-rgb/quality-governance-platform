"""Re-export from canonical domain service.

The single source of truth for policy acknowledgment services lives in
``src.domain.services.policy_acknowledgment``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.policy_acknowledgment import DocumentReadLogService, PolicyAcknowledgmentService

__all__ = ["DocumentReadLogService", "PolicyAcknowledgmentService"]
