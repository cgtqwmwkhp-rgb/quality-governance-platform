"""INV-C11 — CAPA per Why on ``capa_actions`` (DEC-2).

Revision ID: 20261121_inv_c11_capa_why
Revises: 20261120_inv_c7_findings

ADD COLUMN only. No existing column is altered, nothing is dropped, and no
row is rewritten. ``capa_items`` already carried ``five_whys_id`` and
effectiveness review fields for the generic RCA-tools editor; the
investigation register is ``capa_actions``, which only had
``effectiveness_criteria``. This is the expand half: leftover ``why_1``
strings and dual-write readers stay until C18.

The parent is the current chain tip ``20261120_inv_c7_findings``. Revising a
filename that sorts later but is not the head would fork the chain.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261121_inv_c11_capa_why"
down_revision: Union[str, Sequence[str], None] = "20261120_inv_c7_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "capa_actions"
NEW_COLUMNS = (
    "five_whys_id",
    "why_level",
    "effectiveness_review_date",
    "is_effective",
    "effectiveness_notes",
)
FK_NAME = "fk_capa_actions_five_whys_id"
INDEX_NAME = "ix_capa_actions_five_whys_id"
CHECK_NAME = "ck_capa_actions_why_level"


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists() -> bool:
    return _inspector().has_table(TABLE)


def _column_names() -> set[str]:
    if not _table_exists():
        return set()
    return {column["name"] for column in _inspector().get_columns(TABLE)}


def _index_names() -> set[str]:
    if not _table_exists():
        return set()
    return {index["name"] for index in _inspector().get_indexes(TABLE)}


def _fk_names() -> set[str]:
    if not _table_exists():
        return set()
    return {fk["name"] for fk in _inspector().get_foreign_keys(TABLE) if fk.get("name")}


def _ck_names() -> set[str]:
    if not _table_exists():
        return set()
    return {ck["name"] for ck in _inspector().get_check_constraints(TABLE) if ck.get("name")}


def upgrade() -> None:
    if not _table_exists():
        return
    present = _column_names()

    if "five_whys_id" not in present:
        op.add_column(TABLE, sa.Column("five_whys_id", sa.Integer(), nullable=True))
    if "why_level" not in present:
        op.add_column(TABLE, sa.Column("why_level", sa.Integer(), nullable=True))
    if "effectiveness_review_date" not in present:
        op.add_column(
            TABLE,
            sa.Column("effectiveness_review_date", sa.DateTime(timezone=True), nullable=True),
        )
    if "is_effective" not in present:
        op.add_column(TABLE, sa.Column("is_effective", sa.Boolean(), nullable=True))
    if "effectiveness_notes" not in present:
        op.add_column(TABLE, sa.Column("effectiveness_notes", sa.Text(), nullable=True))

    if FK_NAME not in _fk_names() and _inspector().has_table("five_whys_analyses"):
        op.create_foreign_key(
            FK_NAME,
            TABLE,
            "five_whys_analyses",
            ["five_whys_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if INDEX_NAME not in _index_names():
        op.create_index(INDEX_NAME, TABLE, ["five_whys_id"])
    if CHECK_NAME not in _ck_names():
        op.create_check_constraint(
            CHECK_NAME,
            TABLE,
            "why_level IS NULL OR (why_level >= 1 AND why_level <= 20)",
        )


def downgrade() -> None:
    """Drop only the columns this revision added.

    Safe because nothing else depends on them: existing CAPA rows keep their
    investigation ``source_id``, and dual-written ``why_1`` strings are
    untouched. A Why-level link is lost; the CAPA itself is not.
    """
    if not _table_exists():
        return
    if CHECK_NAME in _ck_names():
        op.drop_constraint(CHECK_NAME, TABLE, type_="check")
    if INDEX_NAME in _index_names():
        op.drop_index(INDEX_NAME, table_name=TABLE)
    if FK_NAME in _fk_names():
        op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    present = _column_names()
    for column in reversed(NEW_COLUMNS):
        if column in present:
            op.drop_column(TABLE, column)
