"""Merge regulatory_watch_actions head with document version control.

Revision ID: 20260714_merge_rw_dv
Revises: 20260713_rw_actions, 20260713_doc_ver_ctrl
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260714_merge_rw_dv"
down_revision: Union[str, Sequence[str], None] = (
    "20260713_rw_actions",
    "20260713_doc_ver_ctrl",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
