"""Add missing columns to iso27001_controls table.

Revision ID: iso27001_controls_cols_01
Revises: iso27001_table_fix_01
Create Date: 2026-04-07

The ORM model ISO27001Control (iso27001_controls) was updated to use the
ISO 27001:2022 Annex A attribute taxonomy, but the original migration
(20260120_add_iso27001_isms.py) created the table with an older schema.
This migration adds the columns present in the ORM that are missing from
the database, without dropping legacy columns that may still be in use.

Missing ORM columns added here:
  - control_type                  VARCHAR(50)   nullable
  - information_security_properties  JSON        nullable
  - cybersecurity_concepts         JSON          nullable
  - operational_capabilities       JSON          nullable
  - security_domains               JSON          nullable
  - evidence_required              JSON          nullable
  - evidence_location              TEXT          nullable
  - mapped_standards               JSON          nullable
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "iso27001_controls_cols_01"
down_revision: Union[str, None] = "iso27001_table_fix_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "iso27001_controls"

# (column_name, sa_type, nullable, server_default)
_MISSING_COLUMNS: list[tuple[str, sa.types.TypeEngine, bool, object]] = [
    ("control_type", sa.String(50), True, None),
    ("information_security_properties", sa.JSON(), True, None),
    ("cybersecurity_concepts", sa.JSON(), True, None),
    ("operational_capabilities", sa.JSON(), True, None),
    ("security_domains", sa.JSON(), True, None),
    ("evidence_required", sa.JSON(), True, None),
    ("evidence_location", sa.Text(), True, None),
    ("mapped_standards", sa.JSON(), True, None),
]


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    for col_name, col_type, nullable, server_default in _MISSING_COLUMNS:
        if not _column_exists(_TABLE, col_name):
            kwargs: dict = {"nullable": nullable}
            if server_default is not None:
                kwargs["server_default"] = server_default
            op.add_column(_TABLE, sa.Column(col_name, col_type, **kwargs))


def downgrade() -> None:
    for col_name, _, _, _ in reversed(_MISSING_COLUMNS):
        if _column_exists(_TABLE, col_name):
            op.drop_column(_TABLE, col_name)
