"""Re-export from canonical domain service.

The single source of truth for complaint services lives in
``src.domain.services.complaint_service``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.complaint_service import ComplaintService

__all__ = ["ComplaintService"]
