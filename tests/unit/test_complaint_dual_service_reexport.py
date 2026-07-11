"""Path-to-10: src.services.complaint_service is a dual-service re-export."""

from src.domain.services import complaint_service as domain_mod
from src.services import complaint_service as services_mod


def test_complaint_service_reexport_is_domain_canonical():
    assert services_mod.ComplaintService is domain_mod.ComplaintService
