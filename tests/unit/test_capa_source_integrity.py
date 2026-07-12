"""Regression tests for audit-finding CAPA source integrity."""

from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.exc import IntegrityError

from src.domain.models.capa import CAPAAction

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260712_capa_audit_finding_source_check.py"
PARTIAL_INDEX_MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260406_capa_audit_finding_unique.py"
CONSTRAINT_NAME = "ck_capa_actions_audit_finding_source_id"
CONSTRAINT_SQL = "source_type <> 'audit_finding' OR source_id IS NOT NULL"


def _model_constraint() -> CheckConstraint:
    constraints = {
        constraint.name: constraint
        for constraint in CAPAAction.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    return constraints[CONSTRAINT_NAME]


def test_model_requires_source_id_for_audit_finding_without_polymorphic_fk():
    assert str(_model_constraint().sqltext) == CONSTRAINT_SQL
    assert not CAPAAction.__table__.c.source_id.foreign_keys


def test_constraint_rejects_only_audit_finding_with_null_source_id():
    metadata = MetaData()
    table = Table(
        "capa_source_integrity",
        metadata,
        Column("source_type", String(), nullable=True),
        Column("source_id", Integer(), nullable=True),
        CheckConstraint(CONSTRAINT_SQL, name=CONSTRAINT_NAME),
    )
    engine = create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {"source_type": None, "source_id": None},
                {"source_type": "complaint", "source_id": None},
                {"source_type": "audit_finding", "source_id": 42},
            ],
        )

    with engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            table.insert(),
            {"source_type": "audit_finding", "source_id": None},
        )


def test_migration_chains_from_head_and_preserves_partial_unique_index():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260712_capa_src_check"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_ctl_docs_create"' in migration
    assert f'CONSTRAINT = "{CONSTRAINT_NAME}"' in migration
    assert f'CONSTRAINT_SQL = "{CONSTRAINT_SQL}"' in migration

    partial_index_migration = PARTIAL_INDEX_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "uq_capa_actions_tenant_audit_finding_source" in partial_index_migration
    assert "WHERE source_type = 'audit_finding' AND source_id IS NOT NULL" in partial_index_migration
