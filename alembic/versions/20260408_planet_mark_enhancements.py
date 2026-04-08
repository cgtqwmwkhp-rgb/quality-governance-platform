"""Planet Mark enhancements: evidence storage, certifying_body, action notes.

Revision ID: pm_enhancements_01
Revises: iso27001_schema_drift_02, cel_tenant_unique_01
Create Date: 2026-04-08

Merge migration that combines iso27001_schema_drift_02 and cel_tenant_unique_01
branches, then adds Planet Mark evidence columns:
  - carbon_evidence.file_hash (SHA-256 dedup)
  - carbon_evidence.storage_key (blob path)
  - carbon_reporting_year.certifying_body
  - carbon_improvement_action.notes
  - index on carbon_evidence (file_hash, reporting_year_id, tenant_id)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from typing import Tuple, Union

revision = "pm_enhancements_01"
down_revision: Union[Tuple[str, str], str] = ("iso27001_schema_drift_02", "cel_tenant_unique_01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # carbon_evidence additions (verified_by already exists in model; only add new cols)
    op.add_column("carbon_evidence", sa.Column("file_hash", sa.String(64), nullable=True))
    op.add_column("carbon_evidence", sa.Column("storage_key", sa.String(500), nullable=True))
    op.create_index(
        "ix_carbon_evidence_hash_year",
        "carbon_evidence",
        ["file_hash", "reporting_year_id", "tenant_id"],
    )

    # carbon_reporting_year: certifying body
    op.add_column(
        "carbon_reporting_year",
        sa.Column("certifying_body", sa.String(255), nullable=True, server_default="Planet Mark"),
    )

    # carbon_improvement_action: freetext notes
    op.add_column("carbon_improvement_action", sa.Column("notes", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_index("ix_carbon_evidence_hash_year", table_name="carbon_evidence")
    op.drop_column("carbon_evidence", "storage_key")
    op.drop_column("carbon_evidence", "file_hash")
    op.drop_column("carbon_reporting_year", "certifying_body")
    op.drop_column("carbon_improvement_action", "notes")
