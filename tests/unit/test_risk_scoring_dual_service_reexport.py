"""Path-to-10: src.services.risk_scoring is a dual-service re-export."""

from src.domain.services import risk_scoring as domain_mod
from src.services import risk_scoring as services_mod


def test_risk_scoring_services_reexport_domain_classes():
    assert services_mod.RiskScoringService is domain_mod.RiskScoringService
    assert services_mod.KRIService is domain_mod.KRIService


def test_risk_scoring_service_constructs_with_session():
    class _DummySession:
        pass

    svc = services_mod.RiskScoringService(_DummySession())
    assert svc is not None
    kri = services_mod.KRIService(_DummySession())
    assert kri is not None
