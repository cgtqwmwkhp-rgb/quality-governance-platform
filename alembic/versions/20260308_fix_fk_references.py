"""Fix FK references in document_control and risk_register models.

Revision ID: 20260308_fk_fix
Revises: 20260308_tenant
Create Date: 2026-03-08

Corrects 5 FK references:
- document_control: 3 FKs pointed to document_versions instead of controlled_document_versions
- risk_register: 2 FKs pointed to risk_controls instead of enterprise_risk_controls
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260308_fk_fix"
down_revision: Union[str, None] = "20260308_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_FIXES = [
    {
        "table": "document_approval_instances",
        "column": "version_id",
        "old_ref": "document_versions",
        "new_ref": "controlled_document_versions",
        "old_constraint": "document_approval_instances_version_id_fkey",
    },
    {
        "table": "document_distributions",
        "column": "version_id",
        "old_ref": "document_versions",
        "new_ref": "controlled_document_versions",
        "old_constraint": "document_distributions_version_id_fkey",
    },
    {
        "table": "document_access_logs",
        "column": "version_id",
        "old_ref": "document_versions",
        "new_ref": "controlled_document_versions",
        "old_constraint": "document_access_logs_version_id_fkey",
    },
    {
        "table": "risk_control_mappings",
        "column": "control_id",
        "old_ref": "risk_controls",
        "new_ref": "enterprise_risk_controls",
        "old_constraint": "risk_control_mappings_control_id_fkey",
    },
    {
        "table": "bow_tie_elements",
        "column": "linked_control_id",
        "old_ref": "risk_controls",
        "new_ref": "enterprise_risk_controls",
        "old_constraint": "bow_tie_elements_linked_control_id_fkey",
    },
]


def upgrade() -> None:
    for fix in FK_FIXES:
        op.execute(
            f"ALTER TABLE {fix['table']} "
            f"DROP CONSTRAINT IF EXISTS {fix['old_constraint']}"
        )
        op.execute(
            f"ALTER TABLE {fix['table']} "
            f"ADD CONSTRAINT {fix['old_constraint']} "
            f"FOREIGN KEY ({fix['column']}) REFERENCES {fix['new_ref']}(id)"
        )


def downgrade() -> None:
    for fix in reversed(FK_FIXES):
        op.execute(
            f"ALTER TABLE {fix['table']} "
            f"DROP CONSTRAINT IF EXISTS {fix['old_constraint']}"
        )
        op.execute(
            f"ALTER TABLE {fix['table']} "
            f"ADD CONSTRAINT {fix['old_constraint']} "
            f"FOREIGN KEY ({fix['column']}) REFERENCES {fix['old_ref']}(id)"
        )
