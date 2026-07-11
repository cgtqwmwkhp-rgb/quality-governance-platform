"""Re-export from canonical domain service.

The single source of truth for ReferenceNumberService lives in
``src.domain.services.reference_number``. This module is the Path-to-10 S1
dual-service thin re-export so callers using ``src.services`` keep working.
"""

from src.domain.services.reference_number import ReferenceNumberService

__all__ = ["ReferenceNumberService"]
