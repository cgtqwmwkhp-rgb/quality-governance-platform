"""Add assurance foundation metadata and canonical mapping links.

Revision ID: 20260326_assurance_foundation
Revises: 20260324_case_runner_sheets
Create Date: 2026-03-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260326_assurance_foundation"
down_revision: Union[str, None] = "20260324_case_runner_sheets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_foreign_key(table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    target_columns = set(constrained_columns)
    for fk in inspector.get_foreign_keys(table_name):
        if set(fk.get("constrained_columns") or []) == target_columns and fk.get("referred_table") == referred_table:
            return True
    return False


def upgrade() -> None:
    if _table_exists("audit_runs"):
        if not _has_column("audit_runs", "source_origin"):
            op.add_column("audit_runs", sa.Column("source_origin", sa.String(50), nullable=True))
        if not _has_column("audit_runs", "assurance_scheme"):
            op.add_column("audit_runs", sa.Column("assurance_scheme", sa.String(100), nullable=True))
        if not _has_column("audit_runs", "external_body_name"):
            op.add_column("audit_runs", sa.Column("external_body_name", sa.String(255), nullable=True))
        if not _has_column("audit_runs", "external_auditor_name"):
            op.add_column("audit_runs", sa.Column("external_auditor_name", sa.String(255), nullable=True))
        if not _has_column("audit_runs", "external_reference"):
            op.add_column("audit_runs", sa.Column("external_reference", sa.String(100), nullable=True))
        if not _has_column("audit_runs", "source_document_asset_id"):
            op.add_column("audit_runs", sa.Column("source_document_asset_id", sa.Integer(), nullable=True))
        if not _has_column("audit_runs", "source_document_label"):
            op.add_column("audit_runs", sa.Column("source_document_label", sa.String(255), nullable=True))
        if (
            op.get_bind().dialect.name != "sqlite"
            and _has_column("audit_runs", "source_document_asset_id")
            and not _has_foreign_key("audit_runs", ["source_document_asset_id"], "evidence_assets")
        ):
            op.create_foreign_key(
                "fk_audit_runs_source_document_asset",
                "audit_runs",
                "evidence_assets",
                ["source_document_asset_id"],
                ["id"],
                ondelete="SET NULL",
            )
        op.execute("CREATE INDEX IF NOT EXISTS ix_audit_runs_source_origin ON audit_runs(source_origin)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_audit_runs_assurance_scheme ON audit_runs(assurance_scheme)")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_audit_runs_source_document_asset_id "
            "ON audit_runs(source_document_asset_id)"
        )

    if _table_exists("certificates"):
        if not _has_column("certificates", "primary_evidence_asset_id"):
            op.add_column("certificates", sa.Column("primary_evidence_asset_id", sa.Integer(), nullable=True))
        if (
            op.get_bind().dialect.name != "sqlite"
            and _has_column("certificates", "primary_evidence_asset_id")
            and not _has_foreign_key("certificates", ["primary_evidence_asset_id"], "evidence_assets")
        ):
            op.create_foreign_key(
                "fk_certificates_primary_evidence_asset",
                "certificates",
                "evidence_assets",
                ["primary_evidence_asset_id"],
                ["id"],
                ondelete="SET NULL",
            )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_certificates_primary_evidence_asset_id "
            "ON certificates(primary_evidence_asset_id)"
        )

    if _table_exists("cross_standard_mappings"):
        if not _has_column("cross_standard_mappings", "primary_clause_id"):
            op.add_column("cross_standard_mappings", sa.Column("primary_clause_id", sa.Integer(), nullable=True))
        if not _has_column("cross_standard_mappings", "mapped_clause_id"):
            op.add_column("cross_standard_mappings", sa.Column("mapped_clause_id", sa.Integer(), nullable=True))
        if (
            op.get_bind().dialect.name != "sqlite"
            and _has_column("cross_standard_mappings", "primary_clause_id")
            and not _has_foreign_key("cross_standard_mappings", ["primary_clause_id"], "clauses")
        ):
            op.create_foreign_key(
                "fk_cross_standard_primary_clause",
                "cross_standard_mappings",
                "clauses",
                ["primary_clause_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if (
            op.get_bind().dialect.name != "sqlite"
            and _has_column("cross_standard_mappings", "mapped_clause_id")
            and not _has_foreign_key("cross_standard_mappings", ["mapped_clause_id"], "clauses")
        ):
            op.create_foreign_key(
                "fk_cross_standard_mapped_clause",
                "cross_standard_mappings",
                "clauses",
                ["mapped_clause_id"],
                ["id"],
                ondelete="SET NULL",
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
    if _table_exists("cross_standard_mappings"):
        op.execute("DROP INDEX IF EXISTS ix_cross_standard_mappings_mapped_clause_id")
        op.execute("DROP INDEX IF EXISTS ix_cross_standard_mappings_primary_clause_id")
        if op.get_bind().dialect.name != "sqlite":
            if _has_foreign_key("cross_standard_mappings", ["mapped_clause_id"], "clauses"):
                op.drop_constraint("fk_cross_standard_mapped_clause", "cross_standard_mappings", type_="foreignkey")
            if _has_foreign_key("cross_standard_mappings", ["primary_clause_id"], "clauses"):
                op.drop_constraint("fk_cross_standard_primary_clause", "cross_standard_mappings", type_="foreignkey")
        if _has_column("cross_standard_mappings", "mapped_clause_id"):
            op.drop_column("cross_standard_mappings", "mapped_clause_id")
        if _has_column("cross_standard_mappings", "primary_clause_id"):
            op.drop_column("cross_standard_mappings", "primary_clause_id")

    if _table_exists("certificates"):
        op.execute("DROP INDEX IF EXISTS ix_certificates_primary_evidence_asset_id")
        if op.get_bind().dialect.name != "sqlite" and _has_foreign_key("certificates", ["primary_evidence_asset_id"], "evidence_assets"):
            op.drop_constraint("fk_certificates_primary_evidence_asset", "certificates", type_="foreignkey")
        if _has_column("certificates", "primary_evidence_asset_id"):
            op.drop_column("certificates", "primary_evidence_asset_id")

    if _table_exists("audit_runs"):
        op.execute("DROP INDEX IF EXISTS ix_audit_runs_source_document_asset_id")
        op.execute("DROP INDEX IF EXISTS ix_audit_runs_assurance_scheme")
        op.execute("DROP INDEX IF EXISTS ix_audit_runs_source_origin")
        if op.get_bind().dialect.name != "sqlite" and _has_foreign_key("audit_runs", ["source_document_asset_id"], "evidence_assets"):
            op.drop_constraint("fk_audit_runs_source_document_asset", "audit_runs", type_="foreignkey")
        if _has_column("audit_runs", "source_document_label"):
            op.drop_column("audit_runs", "source_document_label")
        if _has_column("audit_runs", "source_document_asset_id"):
            op.drop_column("audit_runs", "source_document_asset_id")
        if _has_column("audit_runs", "external_reference"):
            op.drop_column("audit_runs", "external_reference")
        if _has_column("audit_runs", "external_auditor_name"):
            op.drop_column("audit_runs", "external_auditor_name")
        if _has_column("audit_runs", "external_body_name"):
            op.drop_column("audit_runs", "external_body_name")
        if _has_column("audit_runs", "assurance_scheme"):
            op.drop_column("audit_runs", "assurance_scheme")
        if _has_column("audit_runs", "source_origin"):
            op.drop_column("audit_runs", "source_origin")
