"""Merge competence_gap and workforce regulatory-watch heads.

Revision ID: 20260714_merge_rw_cg_wf
Revises: 20260714_merge_rw_cg, 20260714_merge_rw_wf
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260714_merge_rw_cg_wf"
down_revision: Union[str, Sequence[str], None] = (
    "20260714_merge_rw_cg",
    "20260714_merge_rw_wf",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
