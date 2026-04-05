"""Enterprise risk import triage model wiring."""

from src.domain.models.risk_register import EnterpriseRisk


def test_enterprise_risk_has_suggestion_triage_status_column() -> None:
    assert "suggestion_triage_status" in EnterpriseRisk.__table__.columns
