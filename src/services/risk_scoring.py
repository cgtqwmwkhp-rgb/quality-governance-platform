"""Re-export from canonical domain service.

The single source of truth for risk scoring / KRI services lives in
``src.domain.services.risk_scoring``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.risk_scoring import KRIService, RiskScoringService

__all__ = ["KRIService", "RiskScoringService"]
