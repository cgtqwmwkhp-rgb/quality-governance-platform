"""Add witnesses_structured JSON column to incidents, near_misses, complaints.

Revision ID: 20260817_case_witnesses_structured
Revises: 20260816_nm_contract_fk
Create Date: 2026-08-17

Generalizes RTA's structured witnesses capture (`witnesses_structured` JSON:
[{ name, phone, email, statement, willing_to_provide_statement }]) onto
Incident, Near Miss, and Complaint so the shared `CaseWitnessesPanel`
component can be wired into every case type's detail page with a real,
persisted backing field. Existing free-text witness fields (Incident.witnesses,
NearMiss.witness_names) are untouched — this is additive.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_case_witnesses_structured"
down_revision: Union[str, Sequence[str], None] = "20260816_nm_contract_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("witnesses_structured", sa.JSON(), nullable=True))
    op.add_column("near_misses", sa.Column("witnesses_structured", sa.JSON(), nullable=True))
    op.add_column("complaints", sa.Column("witnesses_structured", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("complaints", "witnesses_structured")
    op.drop_column("near_misses", "witnesses_structured")
    op.drop_column("incidents", "witnesses_structured")
