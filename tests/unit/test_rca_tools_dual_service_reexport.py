"""Path-to-10 dual-service lane: src.services.rca_tools re-exports domain."""

from src.domain.services import rca_tools as domain_rca
from src.services import rca_tools as legacy_rca


def test_legacy_rca_tools_reexports_domain_classes():
    assert legacy_rca.FiveWhysService is domain_rca.FiveWhysService
    assert legacy_rca.FishboneService is domain_rca.FishboneService
    assert legacy_rca.CAPAService is domain_rca.CAPAService
