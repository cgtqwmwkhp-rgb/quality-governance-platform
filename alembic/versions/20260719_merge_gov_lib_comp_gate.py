"""Merge Governance Library W1 head with campaign competence-gate head.

Revision ID: 20260719_merge_gov_lib_cg
Revises: 20260719_gov_lib_w1_filing, 20260729_campaign_comp_gate
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "20260719_merge_gov_lib_cg"
down_revision: Union[str, Sequence[str], None] = (
    "20260719_gov_lib_w1_filing",
    "20260729_campaign_comp_gate",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op merge of two heads after main + gov-lib W0/W1."""


def downgrade() -> None:
    """No-op merge downgrade."""
