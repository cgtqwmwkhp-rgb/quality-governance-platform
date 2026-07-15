"""Scaffold tests for Wave1a audit DB integrity (models + migration surface)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import UniqueConstraint
from sqlalchemy.schema import ForeignKey

from src.domain.models.audit import AuditResponse, AuditRun

MIGRATION = Path("alembic/versions/20260715_audit_run_response_integrity.py")


def test_audit_run_has_nullable_asset_and_engineer_fks():
    assert hasattr(AuditRun, "asset_id")
    assert hasattr(AuditRun, "engineer_id")

    asset_col = AuditRun.__table__.c.asset_id
    engineer_col = AuditRun.__table__.c.engineer_id
    assert asset_col.nullable is True
    assert engineer_col.nullable is True

    asset_fks = list(asset_col.foreign_keys)
    engineer_fks = list(engineer_col.foreign_keys)
    assert any(fk.column.table.name == "assets" for fk in asset_fks)
    assert any(fk.column.table.name == "engineers" for fk in engineer_fks)
    assert any(fk.ondelete and fk.ondelete.upper() == "SET NULL" for fk in asset_fks)
    assert any(fk.ondelete and fk.ondelete.upper() == "SET NULL" for fk in engineer_fks)


def test_audit_run_has_tenant_asset_and_engineer_indexes():
    index_names = {index.name for index in AuditRun.__table__.indexes}
    assert "ix_audit_runs_tenant_asset" in index_names
    assert "ix_audit_runs_tenant_engineer" in index_names


def test_audit_run_relationships_for_asset_and_engineer():
    assert "asset" in AuditRun.__mapper__.relationships
    assert "engineer" in AuditRun.__mapper__.relationships


def test_audit_response_unique_constraint_on_run_question():
    constraints = [
        constraint for constraint in AuditResponse.__table__.constraints if isinstance(constraint, UniqueConstraint)
    ]
    matching = [
        constraint
        for constraint in constraints
        if constraint.name == "uq_audit_responses_run_question"
        and {col.name for col in constraint.columns} == {"run_id", "question_id"}
    ]
    assert matching, "Expected UniqueConstraint uq_audit_responses_run_question on (run_id, question_id)"


def test_wave1a_migration_scaffold():
    assert MIGRATION.is_file()
    text = MIGRATION.read_text()
    assert 'revision: str = "20260715_audit_db_integrity"' in text
    assert "20260714_e0_promote_async" in text
    assert "DELETE FROM audit_responses AS older" in text
    assert "USING audit_responses AS newer" in text
    assert "uq_audit_responses_run_question" in text
    assert "fk_audit_runs_asset_id" in text
    assert "fk_audit_runs_engineer_id" in text
    assert "ix_audit_runs_tenant_asset" in text
    assert "ix_audit_runs_tenant_engineer" in text
    assert 'ondelete="SET NULL"' in text or "ondelete='SET NULL'" in text


def test_audit_run_fk_targets_are_assets_and_engineers():
    asset_fk: ForeignKey = next(iter(AuditRun.__table__.c.asset_id.foreign_keys))
    engineer_fk: ForeignKey = next(iter(AuditRun.__table__.c.engineer_id.foreign_keys))
    assert asset_fk.column.table.name == "assets"
    assert engineer_fk.column.table.name == "engineers"
