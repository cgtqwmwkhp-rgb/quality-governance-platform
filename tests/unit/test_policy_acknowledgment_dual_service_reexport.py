"""Path-to-10: src.services.policy_acknowledgment is a dual-service re-export."""

from src.domain.services import policy_acknowledgment as domain_mod
from src.services import policy_acknowledgment as services_mod


def test_policy_acknowledgment_services_reexport_domain_classes():
    assert services_mod.PolicyAcknowledgmentService is domain_mod.PolicyAcknowledgmentService
    assert services_mod.DocumentReadLogService is domain_mod.DocumentReadLogService
