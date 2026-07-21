"""Safety AssetType/Location approval_status + source for CES provisional lookups.

Revision ID: 20260804_safety_lu
Revises: 20260803_tm_freq_cr
Create Date: 2026-08-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_safety_lu"
down_revision: Union[str, Sequence[str], None] = "20260803_tm_freq_cr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset_types",
        sa.Column("approval_status", sa.String(length=40), nullable=False, server_default="approved"),
    )
    op.add_column("asset_types", sa.Column("source", sa.String(length=80), nullable=True))
    op.create_index("ix_asset_types_approval_status", "asset_types", ["approval_status"])

    op.add_column(
        "locations",
        sa.Column("approval_status", sa.String(length=40), nullable=False, server_default="approved"),
    )
    op.add_column("locations", sa.Column("source", sa.String(length=80), nullable=True))
    op.create_index("ix_locations_approval_status", "locations", ["approval_status"])


def downgrade() -> None:
    op.drop_index("ix_locations_approval_status", table_name="locations")
    op.drop_column("locations", "source")
    op.drop_column("locations", "approval_status")
    op.drop_index("ix_asset_types_approval_status", table_name="asset_types")
    op.drop_column("asset_types", "source")
    op.drop_column("asset_types", "approval_status")
