"""Compliance Schedule: nullable regulatory standard/clause FKs on requirements.

Revision ID: 20261013_cs_reg_link
Revises: 20261012_rls_sso_prov
Create Date: 2026-10-13

Adds ``regulatory_standard_id`` and ``regulatory_clause_id`` to
``compliance_requirements`` so an accepted AI (or manual) regulatory-basis
suggestion can persist a structured link into the Standards module while the
free-text ``regulatory_basis`` column remains the human-readable citation.

No RLS change is required: ``tenant_isolation`` on ``compliance_requirements``
keys off ``tenant_id``, which is untouched. Adding nullable FK columns needs
no policy rewrite.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_cs_reg_link"
down_revision: Union[str, Sequence[str], None] = "20261012_rls_sso_prov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "compliance_requirements",
        sa.Column("regulatory_standard_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "compliance_requirements",
        sa.Column("regulatory_clause_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_compliance_requirements_regulatory_standard_id",
        "compliance_requirements",
        "standards",
        ["regulatory_standard_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_compliance_requirements_regulatory_clause_id",
        "compliance_requirements",
        "clauses",
        ["regulatory_clause_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_compliance_requirements_regulatory_standard_id",
        "compliance_requirements",
        ["regulatory_standard_id"],
    )
    op.create_index(
        "ix_compliance_requirements_regulatory_clause_id",
        "compliance_requirements",
        ["regulatory_clause_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_compliance_requirements_regulatory_clause_id",
        table_name="compliance_requirements",
    )
    op.drop_index(
        "ix_compliance_requirements_regulatory_standard_id",
        table_name="compliance_requirements",
    )
    op.drop_constraint(
        "fk_compliance_requirements_regulatory_clause_id",
        "compliance_requirements",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_compliance_requirements_regulatory_standard_id",
        "compliance_requirements",
        type_="foreignkey",
    )
    op.drop_column("compliance_requirements", "regulatory_clause_id")
    op.drop_column("compliance_requirements", "regulatory_standard_id")
