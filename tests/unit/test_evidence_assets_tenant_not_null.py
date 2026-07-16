"""Contract tests for evidence_assets tenant NOT NULL fail-safe (R62)."""

from pathlib import Path

from src.domain.models.evidence_asset import EvidenceAsset

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260720_ea_tenant_nn.py"


def test_migration_chains_from_case_risk_jn_and_never_invents_tenant():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260720_ea_tenant_nn"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260719_case_risk_jn"' in body
    assert "Never invent tenant_id=1" in body
    assert "FAIL-SAFE" in body
    assert "should_enforce_not_null" in body
    assert '("audit", "audit_runs")' in body
    assert '("asset", "assets")' in body
    assert "created_by_id" in body


def test_migration_enforces_only_when_zero_nulls():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "def should_enforce_not_null(remaining_null_count: int) -> bool:" in body
    assert "return remaining_null_count == 0" in body


def test_evidence_asset_keeps_tenant_fk_without_forcing_orm_not_null_until_backfill():
    """ORM stays nullable until fail-safe confirms zero orphans; writers must stamp tenant_id."""
    assert EvidenceAsset.__table__.c.tenant_id.nullable is True
    assert any(fk.column.table.name == "tenants" for fk in EvidenceAsset.__table__.c.tenant_id.foreign_keys)
