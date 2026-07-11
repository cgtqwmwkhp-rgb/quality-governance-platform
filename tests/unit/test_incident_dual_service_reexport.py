"""Path-to-10: src.services.incident_service is a dual-service re-export."""

from src.domain.services import incident_service as domain_mod
from src.services import incident_service as services_mod


def test_incident_service_reexport_is_domain_canonical():
    assert services_mod.IncidentService is domain_mod.IncidentService
    assert services_mod.validate_incident_transition is domain_mod.validate_incident_transition
