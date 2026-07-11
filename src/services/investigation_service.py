"""Re-export from canonical domain service.

The single source of truth for investigation services lives in
``src.domain.services.investigation_service``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.investigation_service import InvestigationService, MappingReasonCode

__all__ = ["InvestigationService", "MappingReasonCode"]
