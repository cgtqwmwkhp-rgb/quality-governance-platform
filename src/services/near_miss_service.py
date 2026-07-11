"""Re-export from canonical domain service.

The single source of truth for near-miss services lives in
``src.domain.services.near_miss_service``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.near_miss_service import NearMissService

__all__ = ["NearMissService"]
