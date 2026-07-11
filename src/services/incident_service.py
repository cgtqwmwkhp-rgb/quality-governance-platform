"""Re-export from canonical domain service.

The single source of truth for incident services lives in
``src.domain.services.incident_service``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.
"""

from src.domain.services.incident_service import IncidentService, validate_incident_transition

__all__ = ["IncidentService", "validate_incident_transition"]
