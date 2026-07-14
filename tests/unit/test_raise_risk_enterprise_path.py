"""Guard: near-miss raise-risk must create EnterpriseRisk (risks_v2), not legacy Risk."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEAR_MISS_ROUTE = REPO_ROOT / "src/api/routes/near_miss.py"
HELPERS = REPO_ROOT / "src/domain/services/near_miss_risk_links.py"


def test_raise_risk_route_uses_enterprise_helper() -> None:
    body = NEAR_MISS_ROUTE.read_text(encoding="utf-8")
    assert "create_enterprise_risk_from_near_miss" in body
    assert "from src.domain.models.risk import Risk" not in body
    assert "RaiseRiskFromNearMissResponse" in body
    assert "IntegrityError" in body


def test_enterprise_helper_writes_risks_v2_fields() -> None:
    body = HELPERS.read_text(encoding="utf-8")
    assert "from src.domain.models.risk_register import EnterpriseRisk" in body
    assert "linked_incidents=" in body
    assert "resolve_fk_safe_owner_id" in body
    assert 'source="near_miss"' in body
