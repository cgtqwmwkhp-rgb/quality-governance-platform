"""Regression tests for audit-finding CAPA source integrity (superseded by GT check)."""

from pathlib import Path

from src.domain.models.capa import CAPAAction

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260712_capa_audit_finding_source_check.py"
GT_MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260720_capa_src_chk.py"
PARTIAL_INDEX_MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260406_capa_audit_finding_unique.py"


def test_model_uses_gt_source_check_without_polymorphic_fk():
    names = {c.name for c in CAPAAction.__table__.constraints if getattr(c, "name", None)}
    assert "ck_capa_actions_gt_source_id" in names
    assert "ck_capa_actions_audit_finding_source_id" not in names
    assert not CAPAAction.__table__.c.source_id.foreign_keys


def test_legacy_migration_preserved_and_gt_followup_replaces_constraint():
    legacy = LEGACY_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260712_capa_src_check"' in legacy
    assert "ck_capa_actions_audit_finding_source_id" in legacy

    gt = GT_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260720_capa_src_chk"' in gt
    assert "ck_capa_actions_gt_source_id" in gt
    assert 'OLD_CONSTRAINT = "ck_capa_actions_audit_finding_source_id"' in gt

    partial_index_migration = PARTIAL_INDEX_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "uq_capa_actions_tenant_audit_finding_source" in partial_index_migration
    assert "WHERE source_type = 'audit_finding' AND source_id IS NOT NULL" in partial_index_migration
