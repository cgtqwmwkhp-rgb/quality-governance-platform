"""Re-export from canonical domain service.

The single source of truth for auditor competence services lives in
``src.domain.services.auditor_competence``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.auditor_competence import AuditorCompetenceService

__all__ = ["AuditorCompetenceService"]
