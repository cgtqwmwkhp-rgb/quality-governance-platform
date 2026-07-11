"""Path-to-10: src.services.near_miss_service is a dual-service re-export."""

from src.domain.services import near_miss_service as domain_mod
from src.services import near_miss_service as services_mod


def test_near_miss_service_reexport_is_domain_canonical():
    assert services_mod.NearMissService is domain_mod.NearMissService
