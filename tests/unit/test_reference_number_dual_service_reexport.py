"""Path-to-10: src.services.reference_number is a dual-service re-export."""

from src.domain.services import reference_number as domain_mod
from src.services import reference_number as services_mod


def test_reference_number_service_reexport_is_domain_canonical():
    assert services_mod.ReferenceNumberService is domain_mod.ReferenceNumberService
