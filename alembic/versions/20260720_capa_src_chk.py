"""Expand CAPA source_id CHECK for golden-thread integer sources.

Revision ID: 20260720_capa_src_chk
Revises: 20260720_ea_tenant_nn
Create Date: 2026-07-20

GT-UAT R47: polymorphic CAPA source_id stays without FK. Expand CHECK so
investigation / near_miss / rta / incident / audit_finding require source_id.
Replaces ck_capa_actions_audit_finding_source_id.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_capa_src_chk"
down_revision: Union[str, Sequence[str], None] = "20260720_ea_tenant_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "capa_actions"
OLD_CONSTRAINT = "ck_capa_actions_audit_finding_source_id"
NEW_CONSTRAINT = "ck_capa_actions_gt_source_id"
NEW_CONSTRAINT_SQL = (
    "source_type NOT IN (" "'audit_finding','investigation','near_miss','rta','incident'" ") OR source_id IS NOT NULL"
)
OLD_CONSTRAINT_SQL = "source_type <> 'audit_finding' OR source_id IS NOT NULL"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _constraint_names() -> set[str]:
    if not _inspector().has_table(TABLE):
        return set()
    return {c["name"] for c in _inspector().get_check_constraints(TABLE)}


def _drop_constraint(name: str) -> None:
    if name not in _constraint_names():
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_constraint(name, type_="check")
        return
    op.drop_constraint(name, TABLE, type_="check")


def _create_constraint(name: str, sql: str) -> None:
    if name in _constraint_names():
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.create_check_constraint(name, sql)
        return
    op.create_check_constraint(name, TABLE, sql)


def upgrade() -> None:
    if not _inspector().has_table(TABLE):
        return
    _drop_constraint(OLD_CONSTRAINT)
    _create_constraint(NEW_CONSTRAINT, NEW_CONSTRAINT_SQL)


def downgrade() -> None:
    if not _inspector().has_table(TABLE):
        return
    _drop_constraint(NEW_CONSTRAINT)
    _create_constraint(OLD_CONSTRAINT, OLD_CONSTRAINT_SQL)
