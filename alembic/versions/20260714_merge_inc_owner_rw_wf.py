"""Merge incidents owner_id head with regulatory_watch/workforce merge.

Revision ID: 20260714_merge_inc_rw_wf
Revises: 20260713_inc_owner, 20260714_merge_rw_wf
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260714_merge_inc_rw_wf"
down_revision: Union[str, Sequence[str], None] = (
    "20260713_inc_owner",
    "20260714_merge_rw_wf",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
