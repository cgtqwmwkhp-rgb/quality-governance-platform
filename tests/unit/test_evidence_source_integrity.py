"""Evidence source integrity CHECK + finding↔risk sync contracts (R63/R48)."""

from pathlib import Path

from sqlalchemy import CheckConstraint

from src.domain.models.evidence_asset import EvidenceAsset

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260720_gt_src_sync.py"
CONSTRAINT_NAME = "ck_evidence_assets_source_id_present"
CONSTRAINT_SQL = "source_id IS NOT NULL AND length(trim(source_id)) > 0"


def test_model_has_source_id_presence_check_without_polymorphic_fk():
    constraints = {c.name: c for c in EvidenceAsset.__table__.constraints if isinstance(c, CheckConstraint)}
    assert CONSTRAINT_NAME in constraints
    assert str(constraints[CONSTRAINT_NAME].sqltext) == CONSTRAINT_SQL
    assert not EvidenceAsset.__table__.c.source_id.foreign_keys


def test_migration_chains_and_reports_orphans_without_hard_fk():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260720_gt_src_sync"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260720_capa_src_chk"' in body
    assert CONSTRAINT_NAME in body
    assert "orphan report" in body
    assert "audit_finding_risks" in body
    assert "ON CONFLICT" in body
    assert "no FK enforced" in body
