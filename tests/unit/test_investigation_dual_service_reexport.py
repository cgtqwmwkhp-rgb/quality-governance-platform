"""Path-to-10: src.services.investigation_service is a dual-service re-export."""

from src.domain.services import investigation_service as domain_mod
from src.services import investigation_service as services_mod


def test_investigation_service_reexport_is_domain_canonical():
    assert services_mod.InvestigationService is domain_mod.InvestigationService
    assert services_mod.MappingReasonCode is domain_mod.MappingReasonCode
