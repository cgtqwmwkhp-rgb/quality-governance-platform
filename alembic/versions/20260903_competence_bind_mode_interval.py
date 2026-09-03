"""Bind mode + interval on competence_assessment_binds (CB-UI-2).

Revision ID: 20260903_cb_bind_mode
Revises: 20261119_aud_f5_resp_evid

CB-PR4 shipped one bind per PAMS characteristic. A field assessment and an
induction are two different demonstrations of the same characteristic, so the
characteristic uniqueness moves from ``(tenant, characteristic)`` to
``(tenant, characteristic, mode)``. Template uniqueness is unchanged: one
template is still bound once.

``interval_days`` is nullable on purpose. Null means the bind declares no
interval and the demonstration keeps falling back to the CompetencyRequirement
resolution CB-PR4 already used — it does not mean "never expires".

The parent is the real Alembic head (``alembic heads``), not the filename that
sorts last: ``20260901_*`` chains *after* ``20261118_*`` in this tree.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_cb_bind_mode"
down_revision: Union[str, Sequence[str], None] = "20261119_aud_f5_resp_evid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "competence_assessment_binds"
OLD_CHARACTERISTIC_UQ = "uq_competence_assessment_binds_characteristic"
NEW_CHARACTERISTIC_UQ = "uq_competence_assessment_binds_characteristic_mode"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _unique_names(table_name: str) -> set[str]:
    names = {
        constraint["name"] for constraint in _inspector().get_unique_constraints(table_name) if constraint.get("name")
    }
    # SQLite reports a table-level UNIQUE as an index rather than a constraint.
    names |= {index["name"] for index in _inspector().get_indexes(table_name) if index.get("unique") and index["name"]}
    return names


def upgrade() -> None:
    if not _has_table(TABLE):
        return

    is_postgres = op.get_bind().dialect.name == "postgresql"
    columns = _columns(TABLE)

    if "mode" not in columns:
        # server_default so the NOT NULL add works against rows that already
        # exist; every CB-PR4 bind was a field assessment.
        op.add_column(TABLE, sa.Column("mode", sa.String(length=16), nullable=False, server_default="field"))
        if is_postgres:
            # The model carries no server default; leaving one here is drift.
            op.alter_column(TABLE, "mode", server_default=None)

    if "interval_days" not in columns:
        op.add_column(TABLE, sa.Column("interval_days", sa.Integer(), nullable=True))

    uniques = _unique_names(TABLE)
    if NEW_CHARACTERISTIC_UQ in uniques:
        return

    if is_postgres:
        if OLD_CHARACTERISTIC_UQ in uniques:
            op.drop_constraint(OLD_CHARACTERISTIC_UQ, TABLE, type_="unique")
        op.create_unique_constraint(NEW_CHARACTERISTIC_UQ, TABLE, ["tenant_id", "characteristic_key", "mode"])
        return

    with op.batch_alter_table(TABLE) as batch:
        if OLD_CHARACTERISTIC_UQ in uniques:
            batch.drop_constraint(OLD_CHARACTERISTIC_UQ, type_="unique")
        batch.create_unique_constraint(NEW_CHARACTERISTIC_UQ, ["tenant_id", "characteristic_key", "mode"])


def downgrade() -> None:
    """Reverse the split.

    Restoring ``(tenant, characteristic)`` uniqueness will refuse if a
    characteristic holds both a field and an induction bind by then. That is
    the honest failure: there is no rule for which of the two to discard, and
    silently dropping one would delete an IT-Admin's mapping.
    """
    if not _has_table(TABLE):
        return

    is_postgres = op.get_bind().dialect.name == "postgresql"
    uniques = _unique_names(TABLE)

    if is_postgres:
        if NEW_CHARACTERISTIC_UQ in uniques:
            op.drop_constraint(NEW_CHARACTERISTIC_UQ, TABLE, type_="unique")
        if OLD_CHARACTERISTIC_UQ not in uniques:
            op.create_unique_constraint(OLD_CHARACTERISTIC_UQ, TABLE, ["tenant_id", "characteristic_key"])
    else:
        with op.batch_alter_table(TABLE) as batch:
            if NEW_CHARACTERISTIC_UQ in uniques:
                batch.drop_constraint(NEW_CHARACTERISTIC_UQ, type_="unique")
            if OLD_CHARACTERISTIC_UQ not in uniques:
                batch.create_unique_constraint(OLD_CHARACTERISTIC_UQ, ["tenant_id", "characteristic_key"])

    columns = _columns(TABLE)
    if "interval_days" in columns:
        op.drop_column(TABLE, "interval_days")
    if "mode" in columns:
        op.drop_column(TABLE, "mode")
