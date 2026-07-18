"""Add engineers.qgp_profile_override for QGP-only identity edits.

Revision ID: 20260725_eng_qgp_ov
Revises: 20260724_ds_library_control_fk
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_eng_qgp_ov"
down_revision: Union[str, None] = "20260724_ds_lib_ctrl_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "engineers",
        sa.Column(
            "qgp_profile_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("engineers", "qgp_profile_override")
