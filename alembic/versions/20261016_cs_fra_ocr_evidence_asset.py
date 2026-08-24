"""Add nullable evidence_asset_id to compliance_schedule_ocr_drafts.

Revision ID: 20261016_cs_fra_ocr_ev
Revises: 20261013_cs_fra_ocr
Create Date: 2026-10-16

Slice 4: FRA OCR drafts created from occurrence evidence reuse the evidence
blob. ``evidence_asset_id`` records that link so discard must not delete the
shared storage key. Upload-created drafts keep the column NULL and continue to
own their blob.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_cs_fra_ocr_ev"
down_revision: Union[str, Sequence[str], None] = "20261013_cs_fra_ocr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    if not _inspector().has_table(table):
        return False
    return any(col["name"] == column for col in _inspector().get_columns(table))


def _has_fk(table: str, columns: list[str], referred: str) -> bool:
    if not _inspector().has_table(table):
        return False
    for fk in _inspector().get_foreign_keys(table):
        if fk.get("referred_table") == referred and list(fk.get("constrained_columns") or []) == columns:
            return True
    return False


def _has_index(table: str, name: str) -> bool:
    if not _inspector().has_table(table):
        return False
    return any(idx.get("name") == name for idx in _inspector().get_indexes(table))


def upgrade() -> None:
    table = "compliance_schedule_ocr_drafts"
    if not _inspector().has_table(table):
        return

    if not _has_column(table, "evidence_asset_id"):
        op.add_column(
            table,
            sa.Column("evidence_asset_id", sa.Integer(), nullable=True),
        )

    if op.get_bind().dialect.name != "sqlite" and not _has_fk(table, ["evidence_asset_id"], "evidence_assets"):
        op.create_foreign_key(
            "fk_cs_ocr_drafts_evidence_asset_id",
            table,
            "evidence_assets",
            ["evidence_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_index(table, "ix_cs_ocr_drafts_evidence_asset_id"):
        op.create_index(
            "ix_cs_ocr_drafts_evidence_asset_id",
            table,
            ["evidence_asset_id"],
        )


def downgrade() -> None:
    table = "compliance_schedule_ocr_drafts"
    if not _inspector().has_table(table):
        return

    if _has_index(table, "ix_cs_ocr_drafts_evidence_asset_id"):
        op.drop_index("ix_cs_ocr_drafts_evidence_asset_id", table_name=table)

    if op.get_bind().dialect.name != "sqlite" and _has_fk(table, ["evidence_asset_id"], "evidence_assets"):
        op.drop_constraint("fk_cs_ocr_drafts_evidence_asset_id", table, type_="foreignkey")

    if _has_column(table, "evidence_asset_id"):
        op.drop_column(table, "evidence_asset_id")
