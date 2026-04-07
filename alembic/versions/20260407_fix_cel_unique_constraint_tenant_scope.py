"""Fix compliance_evidence_links unique constraint to include tenant_id.

The original ix_cel_entity_clause unique index (entity_type, entity_id, clause_id)
was not tenant-scoped: two tenants sharing the same entity_id + clause_id combination
would collide. Adding tenant_id as the first column of the unique index ensures
isolation is enforced at the database level.

Revision ID: cel_tenant_unique_01
Revises: portal_source_type_01
Create Date: 2026-04-07
"""

from alembic import op

revision = "cel_tenant_unique_01"
down_revision = "portal_source_type_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old non-tenant-scoped unique index
    op.drop_index("ix_cel_entity_clause", table_name="compliance_evidence_links")

    # Re-create with tenant_id as the leading column so each tenant's evidence
    # links are independently unique — cross-tenant collisions are no longer possible.
    op.create_index(
        "ix_cel_tenant_entity_clause",
        "compliance_evidence_links",
        ["tenant_id", "entity_type", "entity_id", "clause_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_cel_tenant_entity_clause", table_name="compliance_evidence_links")
    op.create_index(
        "ix_cel_entity_clause",
        "compliance_evidence_links",
        ["entity_type", "entity_id", "clause_id"],
        unique=True,
    )
