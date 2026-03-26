"""Add assurance foundation metadata and canonical mapping links.

Revision ID: 20260326_assurance_foundation
Revises: 20260324_case_runner_sheets
Create Date: 2026-03-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260326_assurance_foundation"
down_revision: Union[str, None] = "20260324_case_runner_sheets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS source_origin VARCHAR(50)")
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS assurance_scheme VARCHAR(100)")
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS external_body_name VARCHAR(255)")
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS external_auditor_name VARCHAR(255)")
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS external_reference VARCHAR(100)")
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS source_document_asset_id INTEGER")
    op.execute("ALTER TABLE audit_runs ADD COLUMN IF NOT EXISTS source_document_label VARCHAR(255)")
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE audit_runs "
        "ADD CONSTRAINT fk_audit_runs_source_document_asset "
        "FOREIGN KEY (source_document_asset_id) REFERENCES evidence_assets(id) ON DELETE SET NULL; "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_runs_source_origin ON audit_runs(source_origin)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_runs_assurance_scheme ON audit_runs(assurance_scheme)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_runs_source_document_asset_id "
        "ON audit_runs(source_document_asset_id)"
    )

    op.execute("ALTER TABLE certificates ADD COLUMN IF NOT EXISTS primary_evidence_asset_id INTEGER")
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE certificates "
        "ADD CONSTRAINT fk_certificates_primary_evidence_asset "
        "FOREIGN KEY (primary_evidence_asset_id) REFERENCES evidence_assets(id) ON DELETE SET NULL; "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_certificates_primary_evidence_asset_id "
        "ON certificates(primary_evidence_asset_id)"
    )

    op.execute("ALTER TABLE cross_standard_mappings ADD COLUMN IF NOT EXISTS primary_clause_id INTEGER")
    op.execute("ALTER TABLE cross_standard_mappings ADD COLUMN IF NOT EXISTS mapped_clause_id INTEGER")
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE cross_standard_mappings "
        "ADD CONSTRAINT fk_cross_standard_primary_clause "
        "FOREIGN KEY (primary_clause_id) REFERENCES clauses(id) ON DELETE SET NULL; "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE cross_standard_mappings "
        "ADD CONSTRAINT fk_cross_standard_mapped_clause "
        "FOREIGN KEY (mapped_clause_id) REFERENCES clauses(id) ON DELETE SET NULL; "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cross_standard_mappings_primary_clause_id "
        "ON cross_standard_mappings(primary_clause_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cross_standard_mappings_mapped_clause_id "
        "ON cross_standard_mappings(mapped_clause_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cross_standard_mappings_mapped_clause_id")
    op.execute("DROP INDEX IF EXISTS ix_cross_standard_mappings_primary_clause_id")
    op.execute(
        "ALTER TABLE cross_standard_mappings DROP CONSTRAINT IF EXISTS fk_cross_standard_mapped_clause"
    )
    op.execute(
        "ALTER TABLE cross_standard_mappings DROP CONSTRAINT IF EXISTS fk_cross_standard_primary_clause"
    )
    op.execute("ALTER TABLE cross_standard_mappings DROP COLUMN IF EXISTS mapped_clause_id")
    op.execute("ALTER TABLE cross_standard_mappings DROP COLUMN IF EXISTS primary_clause_id")

    op.execute("DROP INDEX IF EXISTS ix_certificates_primary_evidence_asset_id")
    op.execute(
        "ALTER TABLE certificates DROP CONSTRAINT IF EXISTS fk_certificates_primary_evidence_asset"
    )
    op.execute("ALTER TABLE certificates DROP COLUMN IF EXISTS primary_evidence_asset_id")

    op.execute("DROP INDEX IF EXISTS ix_audit_runs_source_document_asset_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_runs_assurance_scheme")
    op.execute("DROP INDEX IF EXISTS ix_audit_runs_source_origin")
    op.execute(
        "ALTER TABLE audit_runs DROP CONSTRAINT IF EXISTS fk_audit_runs_source_document_asset"
    )
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS source_document_label")
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS source_document_asset_id")
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS external_reference")
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS external_auditor_name")
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS external_body_name")
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS assurance_scheme")
    op.execute("ALTER TABLE audit_runs DROP COLUMN IF EXISTS source_origin")
