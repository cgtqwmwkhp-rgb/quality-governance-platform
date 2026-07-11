"""Re-export from canonical domain service.

The single source of truth for executive dashboard services lives in
``src.domain.services.executive_dashboard``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.executive_dashboard import ExecutiveDashboardService

__all__ = ["ExecutiveDashboardService"]
