"""Re-export from canonical domain service.

The single source of truth for CAPA services lives in
``src.domain.services.capa_service``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.capa_service import CAPAService

__all__ = ["CAPAService"]
