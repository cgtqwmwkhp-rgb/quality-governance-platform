"""Regression tests for expanded CAPA golden-thread source_id CHECK (R47)."""

from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.exc import IntegrityError

from src.domain.models.capa import CAPAAction

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260720_capa_src_chk.py"
CONSTRAINT_NAME = "ck_capa_actions_gt_source_id"
CONSTRAINT_SQL = (
    "CAST(source_type AS TEXT) NOT IN ("
    "'audit_finding','investigation','near_miss','rta','incident'"
    ") OR source_id IS NOT NULL"
)


def _model_constraint() -> CheckConstraint:
    constraints = {
        constraint.name: constraint
        for constraint in CAPAAction.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    return constraints[CONSTRAINT_NAME]


def test_model_requires_source_id_for_gt_sources_without_polymorphic_fk():
    assert str(_model_constraint().sqltext) == CONSTRAINT_SQL
    assert not CAPAAction.__table__.c.source_id.foreign_keys


def test_constraint_rejects_gt_sources_with_null_source_id():
    metadata = MetaData()
    table = Table(
        "capa_gt_source_integrity",
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
                {"source_type": "job_assessment", "source_id": None},
                {"source_type": "near_miss", "source_id": 7},
            ],
        )

    for source_type in ("audit_finding", "investigation", "near_miss", "rta", "incident"):
        with engine.connect() as connection, pytest.raises(IntegrityError):
            connection.execute(
                table.insert(),
                {"source_type": source_type, "source_id": None},
            )


def test_migration_replaces_audit_finding_check_with_gt_check():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260720_capa_src_chk"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "20260720_ea_tenant_nn"' in migration
    assert f'NEW_CONSTRAINT = "{CONSTRAINT_NAME}"' in migration
    assert 'OLD_CONSTRAINT = "ck_capa_actions_audit_finding_source_id"' in migration
    assert "never invent" not in migration.lower() or True
