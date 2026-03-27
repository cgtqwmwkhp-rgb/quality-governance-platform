"""Normalize JSON array columns into proper junction tables.

Revision ID: a1b2c3d4e5f6
Revises: 20260220_notifications
Create Date: 2026-02-20

Creates junction tables for many-to-many relationships that were previously
stored as JSON arrays, migrates existing data, and renames the original
columns with a ``_legacy`` suffix.

Junction tables created:
  - risk_clause_mapping        (risks.clause_ids_json)
  - risk_control_mapping       (risks.control_ids_json)
  - risk_audit_mapping         (risks.linked_audit_ids_json)
  - risk_incident_mapping      (risks.linked_incident_ids_json)
  - audit_finding_clause_mapping (audit_findings.clause_ids_json)
  - audit_section_clause_mapping (new — no prior JSON column)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "20260220_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_junction_table(
    table_name: str,
    fk1_col: str,
    fk1_ref: str,
    fk2_col: str,
    fk2_ref: str,
    uq_name: str,
) -> None:
    """Helper to create a junction table with standard structure."""
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(fk1_col, sa.Integer(), nullable=False),
        sa.Column(fk2_col, sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint([fk1_col], [fk1_ref], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([fk2_col], [fk2_ref], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(fk1_col, fk2_col, name=uq_name),
    )
    op.create_index(f"ix_{table_name}_{fk1_col}", table_name, [fk1_col])
    op.create_index(f"ix_{table_name}_{fk2_col}", table_name, [fk2_col])


def _migrate_json_array_column(
    source_table: str,
    source_id_col: str,
    source_json_col: str,
    target_table: str,
    target_left_col: str,
    target_right_col: str,
) -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "postgresql":
        sql = f"""
            INSERT INTO {target_table} ({target_left_col}, {target_right_col})
            SELECT src.{source_id_col}, CAST(je.value AS INTEGER)
            FROM {source_table} AS src,
                 json_array_elements_text(src.{source_json_col}) AS je(value)
            WHERE src.{source_json_col} IS NOT NULL
              AND CAST(src.{source_json_col} AS TEXT) NOT IN ('[]', 'null')
            ON CONFLICT DO NOTHING
        """
    else:
        sql = f"""
            INSERT OR IGNORE INTO {target_table} ({target_left_col}, {target_right_col})
            SELECT src.{source_id_col}, CAST(je.value AS INTEGER)
            FROM {source_table} AS src
            JOIN json_each(src.{source_json_col}) AS je
            WHERE src.{source_json_col} IS NOT NULL
              AND CAST(src.{source_json_col} AS TEXT) NOT IN ('[]', 'null')
        """

    op.execute(sa.text(sql))


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Create junction tables                                          #
    # ------------------------------------------------------------------ #
    _create_junction_table(
        "risk_clause_mapping",
        "risk_id", "risks.id",
        "clause_id", "clauses.id",
        "uq_risk_clause",
    )
    _create_junction_table(
        "risk_control_mapping",
        "risk_id", "risks.id",
        "control_id", "controls.id",
        "uq_risk_control",
    )
    _create_junction_table(
        "risk_audit_mapping",
        "risk_id", "risks.id",
        "audit_id", "audit_runs.id",
        "uq_risk_audit",
    )
    _create_junction_table(
        "risk_incident_mapping",
        "risk_id", "risks.id",
        "incident_id", "incidents.id",
        "uq_risk_incident",
    )
    _create_junction_table(
        "audit_finding_clause_mapping",
        "finding_id", "audit_findings.id",
        "clause_id", "clauses.id",
        "uq_finding_clause",
    )
    _create_junction_table(
        "audit_section_clause_mapping",
        "section_id", "audit_sections.id",
        "clause_id", "clauses.id",
        "uq_section_clause",
    )

    # ------------------------------------------------------------------ #
    # 2. Migrate data from JSON columns into junction tables             #
    # ------------------------------------------------------------------ #

    # risks.clause_ids_json → risk_clause_mapping
    _migrate_json_array_column(
        "risks",
        "id",
        "clause_ids_json",
        "risk_clause_mapping",
        "risk_id",
        "clause_id",
    )

    # risks.control_ids_json → risk_control_mapping
    _migrate_json_array_column(
        "risks",
        "id",
        "control_ids_json",
        "risk_control_mapping",
        "risk_id",
        "control_id",
    )

    # risks.linked_audit_ids_json → risk_audit_mapping
    _migrate_json_array_column(
        "risks",
        "id",
        "linked_audit_ids_json",
        "risk_audit_mapping",
        "risk_id",
        "audit_id",
    )

    # risks.linked_incident_ids_json → risk_incident_mapping
    _migrate_json_array_column(
        "risks",
        "id",
        "linked_incident_ids_json",
        "risk_incident_mapping",
        "risk_id",
        "incident_id",
    )

    # audit_findings.clause_ids_json → audit_finding_clause_mapping
    _migrate_json_array_column(
        "audit_findings",
        "id",
        "clause_ids_json",
        "audit_finding_clause_mapping",
        "finding_id",
        "clause_id",
    )

    # audit_section_clause_mapping — no source JSON column on audit_sections,
    # so no data migration needed.  The table is ready for application use.

    # ------------------------------------------------------------------ #
    # 3. Rename original JSON columns to _legacy suffix                  #
    # ------------------------------------------------------------------ #
    op.alter_column("risks", "clause_ids_json",
                    new_column_name="clause_ids_json_legacy")
    op.alter_column("risks", "control_ids_json",
                    new_column_name="control_ids_json_legacy")
    op.alter_column("risks", "linked_audit_ids_json",
                    new_column_name="linked_audit_ids_json_legacy")
    op.alter_column("risks", "linked_incident_ids_json",
                    new_column_name="linked_incident_ids_json_legacy")
    op.alter_column("audit_findings", "clause_ids_json",
                    new_column_name="clause_ids_json_legacy")


def downgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Rename _legacy columns back to original names                   #
    # ------------------------------------------------------------------ #
    op.alter_column("audit_findings", "clause_ids_json_legacy",
                    new_column_name="clause_ids_json")
    op.alter_column("risks", "linked_incident_ids_json_legacy",
                    new_column_name="linked_incident_ids_json")
    op.alter_column("risks", "linked_audit_ids_json_legacy",
                    new_column_name="linked_audit_ids_json")
    op.alter_column("risks", "control_ids_json_legacy",
                    new_column_name="control_ids_json")
    op.alter_column("risks", "clause_ids_json_legacy",
                    new_column_name="clause_ids_json")

    # ------------------------------------------------------------------ #
    # 2. Drop junction tables (reverse creation order)                   #
    # ------------------------------------------------------------------ #
    op.drop_index("ix_audit_section_clause_mapping_clause_id",
                  table_name="audit_section_clause_mapping")
    op.drop_index("ix_audit_section_clause_mapping_section_id",
                  table_name="audit_section_clause_mapping")
    op.drop_table("audit_section_clause_mapping")

    op.drop_index("ix_audit_finding_clause_mapping_clause_id",
                  table_name="audit_finding_clause_mapping")
    op.drop_index("ix_audit_finding_clause_mapping_finding_id",
                  table_name="audit_finding_clause_mapping")
    op.drop_table("audit_finding_clause_mapping")

    op.drop_index("ix_risk_incident_mapping_incident_id",
                  table_name="risk_incident_mapping")
    op.drop_index("ix_risk_incident_mapping_risk_id",
                  table_name="risk_incident_mapping")
    op.drop_table("risk_incident_mapping")

    op.drop_index("ix_risk_audit_mapping_audit_id",
                  table_name="risk_audit_mapping")
    op.drop_index("ix_risk_audit_mapping_risk_id",
                  table_name="risk_audit_mapping")
    op.drop_table("risk_audit_mapping")

    op.drop_index("ix_risk_control_mapping_control_id",
                  table_name="risk_control_mapping")
    op.drop_index("ix_risk_control_mapping_risk_id",
                  table_name="risk_control_mapping")
    op.drop_table("risk_control_mapping")

    op.drop_index("ix_risk_clause_mapping_clause_id",
                  table_name="risk_clause_mapping")
    op.drop_index("ix_risk_clause_mapping_risk_id",
                  table_name="risk_clause_mapping")
    op.drop_table("risk_clause_mapping")
