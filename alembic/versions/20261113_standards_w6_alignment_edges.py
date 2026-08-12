"""Int-W6 — alignment edge provenance + coverage declarations.

Revision ID: 20261113_standards_w6_edges
Revises: 20261112_standards_w5_axes

Additive columns only. The v1.1 5064 payload (CE↔CE+ NEAR pairs) is applied
through the existing import/seed path, not by rewriting live edges here.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261113_standards_w6_edges"
down_revision: Union[str, Sequence[str], None] = "20261112_standards_w5_axes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matrix_versions",
        sa.Column("coverage_declarations", sa.JSON(), nullable=True),
    )
    op.add_column(
        "alignment_edges",
        sa.Column("source_authority", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alignment_edges", "source_authority")
    op.drop_column("matrix_versions", "coverage_declarations")
