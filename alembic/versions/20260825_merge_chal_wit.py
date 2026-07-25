"""Merge audit challenge head with H&S witnesses_structured head.

Revision ID: 20260825_merge_chal_wit
Revises: 20260816_audit_challenge, 20260817_wit_struct
Create Date: 2026-08-25

Revision id kept ≤32 chars for alembic_version.version_num VARCHAR(32).
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "20260825_merge_chal_wit"
down_revision: Union[str, Sequence[str], None] = (
    "20260816_audit_challenge",
    "20260817_wit_struct",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op merge of coach + H&S rich reporting heads after main merge."""


def downgrade() -> None:
    """No-op merge downgrade."""
