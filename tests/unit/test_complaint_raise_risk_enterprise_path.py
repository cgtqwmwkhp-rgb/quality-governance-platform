"""Guard: complaint raise-risk must create EnterpriseRisk (risks_v2), not legacy Risk."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLAINT_ROUTE = REPO_ROOT / "src/api/routes/complaints.py"
HELPERS = REPO_ROOT / "src/domain/services/complaint_risk_links.py"


def test_raise_risk_route_uses_enterprise_helper() -> None:
    body = COMPLAINT_ROUTE.read_text(encoding="utf-8")
    assert "create_enterprise_risk_from_complaint" in body
    assert "from src.domain.models.risk import Risk" not in body
    assert "RaiseRiskFromComplaintResponse" in body
    assert "IntegrityError" in body
    assert 'require_permission("risk:create")' in body


def test_enterprise_helper_writes_risks_v2_fields() -> None:
    body = HELPERS.read_text(encoding="utf-8")
    assert "from src.domain.models.risk_register import EnterpriseRisk" in body
    assert "linked_incidents=" in body
    assert "resolve_fk_safe_owner_id" in body
    assert 'source="complaint"' in body
    assert 'case_type="complaint"' in body


def test_complaint_response_exposes_linked_risk_ids() -> None:
    schema = (REPO_ROOT / "src/api/schemas/complaint.py").read_text(encoding="utf-8")
    assert "linked_risk_ids: Optional[str] = None" in schema
