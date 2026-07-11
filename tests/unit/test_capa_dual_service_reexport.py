"""Path-to-10: src.services.capa_service is a dual-service re-export."""

from src.domain.services import capa_service as domain_mod
from src.services import capa_service as services_mod


def test_capa_service_reexport_is_domain_canonical():
    assert services_mod.CAPAService is domain_mod.CAPAService
