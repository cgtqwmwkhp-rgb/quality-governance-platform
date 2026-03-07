"""Re-export from canonical domain service.

The single source of truth for ReferenceNumberService lives in
``src.domain.services.reference_number``.  This module re-exports it
so that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.reference_number import ReferenceNumberService

__all__ = ["ReferenceNumberService"]
