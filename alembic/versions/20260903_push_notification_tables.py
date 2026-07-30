"""Create push_subscriptions and notification_logs (C-67).

Revision ID: 20260903_push_notif
Revises: 20260902_capa_vd_src
Create Date: 2026-09-03

These tables were declared on SQLAlchemy models living in an API route module,
so alembic/env.py never saw them and no migration existed. This revision matches
the models exactly (no extra indexes) so the drift ratchet stays quiet.

Per-table idempotency, and why it is not optional
------------------------------------------------
The first production run of this revision aborted with ``DuplicateTableError:
relation "push_subscriptions" already exists``. Production carried both tables
with no ``alembic_version`` row for this revision -- a ``create_all`` leftover
from the years these models sat in a route module. The original note here said
staging and production both lacked the tables; that was true of staging and
wrong about production, and an unconditional ``CREATE TABLE`` had no way to say
so. Each table is therefore created only when it is absent, and each is decided
independently: one of the pair existing says nothing about the other.

Adoption is checked, not assumed
--------------------------------
An already-present table is adopted rather than recreated, but only after its
columns are compared against the ones this revision would have created. Stamping
the revision over a table of some other shape would record the schema as
migrated while every read of the entity still failed -- the same class of silent
wrongness that produced this incident, and worse than the DuplicateTable it
replaces. Extra columns are tolerated: they are drift no gate can see from here,
and they do not stop the models reading the table.

The comparison is columns only. Constraints are not re-checked because
``create_all`` emits the ``UNIQUE (endpoint)`` alongside the columns, so a table
of that provenance carries it, and issuing DDL against live production data on
the strength of an inference is the larger risk.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_push_notif"
down_revision: Union[str, Sequence[str], None] = "20260902_capa_vd_src"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _push_subscriptions_columns() -> tuple[sa.Column, ...]:
    """Built per call: a Column may only ever be attached to one Table."""
    return (
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.String(length=255), nullable=False),
        sa.Column("auth_key", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )


def _notification_logs_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def _missing_columns(inspector: sa.Inspector, table: str, expected: Sequence[str]) -> list[str]:
    present = {column["name"] for column in inspector.get_columns(table)}
    return [name for name in expected if name not in present]


def _adopt(inspector: sa.Inspector, table: str, expected: Sequence[str]) -> None:
    """Accept a table this revision did not create, or refuse it loudly."""
    missing = _missing_columns(inspector, table, expected)
    if missing:
        raise RuntimeError(
            f"{table!r} already exists but does not carry {missing}, so "
            f"{revision} cannot adopt it: stamping the revision here would record "
            "a schema the models cannot read as migrated. Reconcile the table by "
            "hand -- or drop it if it holds nothing worth keeping -- and re-run."
        )


def _create_or_adopt(table: str, columns: tuple[sa.Column, ...], *constraints: sa.schema.SchemaItem) -> None:
    """Create the table, or take ownership of one that is already there.

    Which of the two happened is printed, because it is the only record that a
    given environment held orphan tables: after this revision is stamped the two
    cases are indistinguishable in the schema.
    """
    inspector = _inspector()
    if inspector.has_table(table):
        _adopt(inspector, table, [column.name for column in columns])
        print(f"{revision}: adopted the existing {table!r}; its columns match, so it was not recreated")
        return
    op.create_table(table, *columns, *constraints)
    print(f"{revision}: created {table!r}")


def upgrade() -> None:
    _create_or_adopt(
        "push_subscriptions",
        _push_subscriptions_columns(),
        sa.UniqueConstraint("endpoint"),
    )
    _create_or_adopt("notification_logs", _notification_logs_columns())


def downgrade() -> None:
    inspector = _inspector()
    for table in ("notification_logs", "push_subscriptions"):
        if inspector.has_table(table):
            op.drop_table(table)
