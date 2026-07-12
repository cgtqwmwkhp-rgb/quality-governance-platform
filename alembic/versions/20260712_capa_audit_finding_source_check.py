"""Require audit-finding CAPAs to identify their source row.

Revision ID: 20260712_capa_src_check
Revises: 20260711_ctl_docs_create
Create Date: 2026-07-12

The source_id column is intentionally polymorphic. This CHECK enforces the
required identifier for audit-finding CAPAs without adding a foreign key.
The existing tenant-scoped partial unique index remains unchanged.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_capa_src_check"
down_revision: Union[str, Sequence[str], None] = "20260711_ctl_docs_create"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "capa_actions"
CONSTRAINT = "ck_capa_actions_audit_finding_source_id"
CONSTRAINT_SQL = "source_type <> 'audit_finding' OR source_id IS NOT NULL"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_constraint() -> bool:
    return CONSTRAINT in {constraint["name"] for constraint in _inspector().get_check_constraints(TABLE)}


def upgrade() -> None:
    if _has_constraint():
        return

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.create_check_constraint(CONSTRAINT, CONSTRAINT_SQL)
        return

    op.create_check_constraint(CONSTRAINT, TABLE, CONSTRAINT_SQL)


def downgrade() -> None:
    if not _has_constraint():
        return

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_constraint(CONSTRAINT, type_="check")
        return

    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
