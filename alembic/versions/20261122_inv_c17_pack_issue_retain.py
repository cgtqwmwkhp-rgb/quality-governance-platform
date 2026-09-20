"""INV-C17 — gate pack issue and retain the issued PDF (DEC-4 + DEC-5).

Revision ID: 20261122_inv_c17_issue
Revises: 20261121_inv_c11_capa_why

Additive only. Seven nullable columns on ``investigation_customer_packs``
(redaction review + the retained PDF pointer) and one new table,
``investigation_pack_disclosures``, recording who each pack was issued to.

Nothing existing is altered or rewritten: a pack generated before this
revision reads as "no review, never issued", which is the truth about it. The
parent is the current chain tip ``20261121_inv_c11_capa_why``; revising a
filename that sorts later but is not the head would fork the chain.

Every step is existence-guarded so a re-run, or a database where an earlier
attempt got part-way, converges instead of failing.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261122_inv_c17_issue"
down_revision: Union[str, Sequence[str], None] = "20261121_inv_c11_capa_why"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PACKS_TABLE = "investigation_customer_packs"
DISCLOSURES_TABLE = "investigation_pack_disclosures"

NEW_COLUMNS = (
    "redaction_review_cleared_at",
    "redaction_review_by_id",
    "redaction_review_at",
    "redaction_review_note",
    "issued_at",
    "issued_by_id",
    "issued_pdf_asset_id",
    "issued_pdf_storage_key",
    "issued_pdf_sha256",
    "issued_pdf_size_bytes",
)

REVIEW_BY_FK = "fk_inv_packs_redaction_review_by_id"
ISSUED_BY_FK = "fk_inv_packs_issued_by_id"
ISSUED_ASSET_FK = "fk_inv_packs_issued_pdf_asset_id"
ISSUED_ASSET_INDEX = "ix_investigation_customer_packs_issued_pdf_asset_id"

DISCLOSURE_INDEXES = (
    ("ix_investigation_pack_disclosures_tenant_id", "tenant_id"),
    ("ix_investigation_pack_disclosures_investigation_id", "investigation_id"),
    ("ix_investigation_pack_disclosures_pack_id", "pack_id"),
    # TimestampMixin declares created_at index=True; omitting it here would show
    # up as CreateIndexOp drift on a table that has none.
    ("ix_investigation_pack_disclosures_created_at", "created_at"),
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _inspector().has_table(name)


def _column_names(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {column["name"] for column in _inspector().get_columns(table)}


def _index_names(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {index["name"] for index in _inspector().get_indexes(table)}


def _fk_names(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {fk["name"] for fk in _inspector().get_foreign_keys(table) if fk.get("name")}


def upgrade() -> None:
    if _has_table(PACKS_TABLE):
        present = _column_names(PACKS_TABLE)

        if "redaction_review_cleared_at" not in present:
            op.add_column(
                PACKS_TABLE,
                sa.Column("redaction_review_cleared_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "redaction_review_by_id" not in present:
            op.add_column(PACKS_TABLE, sa.Column("redaction_review_by_id", sa.Integer(), nullable=True))
        if "redaction_review_at" not in present:
            op.add_column(
                PACKS_TABLE,
                sa.Column("redaction_review_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "redaction_review_note" not in present:
            op.add_column(PACKS_TABLE, sa.Column("redaction_review_note", sa.Text(), nullable=True))
        if "issued_at" not in present:
            op.add_column(PACKS_TABLE, sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True))
        if "issued_by_id" not in present:
            op.add_column(PACKS_TABLE, sa.Column("issued_by_id", sa.Integer(), nullable=True))
        if "issued_pdf_asset_id" not in present:
            op.add_column(PACKS_TABLE, sa.Column("issued_pdf_asset_id", sa.Integer(), nullable=True))
        if "issued_pdf_storage_key" not in present:
            op.add_column(PACKS_TABLE, sa.Column("issued_pdf_storage_key", sa.String(length=500), nullable=True))
        if "issued_pdf_sha256" not in present:
            op.add_column(PACKS_TABLE, sa.Column("issued_pdf_sha256", sa.String(length=64), nullable=True))
        if "issued_pdf_size_bytes" not in present:
            op.add_column(PACKS_TABLE, sa.Column("issued_pdf_size_bytes", sa.Integer(), nullable=True))

        existing_fks = _fk_names(PACKS_TABLE)
        if REVIEW_BY_FK not in existing_fks and _has_table("users"):
            op.create_foreign_key(REVIEW_BY_FK, PACKS_TABLE, "users", ["redaction_review_by_id"], ["id"])
        if ISSUED_BY_FK not in existing_fks and _has_table("users"):
            op.create_foreign_key(ISSUED_BY_FK, PACKS_TABLE, "users", ["issued_by_id"], ["id"])
        if ISSUED_ASSET_FK not in existing_fks and _has_table("evidence_assets"):
            op.create_foreign_key(
                ISSUED_ASSET_FK,
                PACKS_TABLE,
                "evidence_assets",
                ["issued_pdf_asset_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if ISSUED_ASSET_INDEX not in _index_names(PACKS_TABLE):
            op.create_index(ISSUED_ASSET_INDEX, PACKS_TABLE, ["issued_pdf_asset_id"])

    if not _has_table(DISCLOSURES_TABLE):
        op.create_table(
            DISCLOSURES_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("investigation_id", sa.Integer(), nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=False),
            sa.Column("recipient", sa.String(length=300), nullable=False),
            sa.Column("recipient_email", sa.String(length=320), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("pdf_sha256", sa.String(length=64), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            # ``sa.func.now()`` rather than ``sa.text("now()")``: it compiles to now()
            # on PostgreSQL exactly as the ORM's server_default does, and to
            # CURRENT_TIMESTAMP on SQLite, so the revision is runnable in both.
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["investigation_id"], ["investigation_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["pack_id"], [f"{PACKS_TABLE}.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if _has_table(DISCLOSURES_TABLE):
        existing_indexes = _index_names(DISCLOSURES_TABLE)
        for index_name, column in DISCLOSURE_INDEXES:
            if index_name not in existing_indexes:
                op.create_index(index_name, DISCLOSURES_TABLE, [column])


def downgrade() -> None:
    """Drop only what this revision created.

    The disclosure log and the pointer to the retained PDF go; the retained PDF
    itself is an ``evidence_assets`` row written by the application and is left
    alone, because deleting a document a customer was given is not a schema
    rollback. Packs, their content and their checksums are untouched.
    """
    if _has_table(DISCLOSURES_TABLE):
        op.drop_table(DISCLOSURES_TABLE)

    if not _has_table(PACKS_TABLE):
        return

    if ISSUED_ASSET_INDEX in _index_names(PACKS_TABLE):
        op.drop_index(ISSUED_ASSET_INDEX, table_name=PACKS_TABLE)
    existing_fks = _fk_names(PACKS_TABLE)
    for fk_name in (ISSUED_ASSET_FK, ISSUED_BY_FK, REVIEW_BY_FK):
        if fk_name in existing_fks:
            op.drop_constraint(fk_name, PACKS_TABLE, type_="foreignkey")

    present = _column_names(PACKS_TABLE)
    for column in reversed(NEW_COLUMNS):
        if column in present:
            op.drop_column(PACKS_TABLE, column)
