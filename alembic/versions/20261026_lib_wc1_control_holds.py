"""WC-1 / L-40: documents.legal_matter_reference — hold scope on the Register.

Revision ID: 20261026_lib_wc1_control_holds
Revises: 20261025_lib_wa2_functions_pel
Create Date: 2026-08-09

``matter_legal_holds`` (20260720) stays the sole hold register: this column only
records which matter a Register document is filed under, so a hold issued on
that matter can be resolved to the documents it freezes. No hold state is
duplicated here — status still lives on the hold row — and no second hold table
is introduced.

Additive and nullable. NULL means the document is filed under no legal matter,
which is a positive fact rather than an unknown, so it is not backfilled.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_lib_wc1_control_holds"
down_revision: Union[str, Sequence[str], None] = "20261025_lib_wa2_functions_pel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_documents_tenant_legal_matter_reference"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _column_exists(table: str, column: str) -> bool:
    if not _inspector().has_table(table):
        return False
    return any(c["name"] == column for c in _inspector().get_columns(table))


def _index_exists(table: str, index: str) -> bool:
    if not _inspector().has_table(table):
        return False
    return any(i["name"] == index for i in _inspector().get_indexes(table))


def upgrade() -> None:
    if not _column_exists("documents", "legal_matter_reference"):
        op.add_column(
            "documents",
            sa.Column("legal_matter_reference", sa.String(length=128), nullable=True),
        )
    if not _index_exists("documents", _INDEX):
        # The enforcement read is always (tenant_id, matter_reference): a hold is
        # tenant-scoped, so the tenant column has to lead for the index to be used.
        op.create_index(
            _INDEX,
            "documents",
            ["tenant_id", "legal_matter_reference"],
        )


def downgrade() -> None:
    if _index_exists("documents", _INDEX):
        op.drop_index(_INDEX, table_name="documents")
    if _column_exists("documents", "legal_matter_reference"):
        op.drop_column("documents", "legal_matter_reference")
