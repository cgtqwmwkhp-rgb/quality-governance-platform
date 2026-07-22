"""Copy contracts→customers and roles→workforce_roles lookup options.

Revision ID: 20260806_catalog_ssot
Revises: 20260805_audit_branch_rpt
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260806_catalog_ssot"
down_revision: Union[str, Sequence[str], None] = "20260805_audit_branch_rpt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Contracts table → lookup_options.customers (stable codes; skip duplicates).
    op.execute(
        """
        INSERT INTO lookup_options (
            tenant_id, category, code, label, description, is_active, display_order,
            created_at, updated_at
        )
        SELECT
            c.tenant_id,
            'customers',
            c.code,
            COALESCE(NULLIF(TRIM(c.name), ''), c.code),
            COALESCE(c.description, c.client_name),
            COALESCE(c.is_active, true),
            COALESCE(c.display_order, 0),
            NOW(),
            NOW()
        FROM contracts c
        WHERE NOT EXISTS (
            SELECT 1 FROM lookup_options l
            WHERE l.category = 'customers'
              AND l.code = c.code
              AND l.tenant_id IS NOT DISTINCT FROM c.tenant_id
        )
        """
    )

    # Legacy roles seed → workforce_roles (Admin Lookups SSOT).
    op.execute(
        """
        INSERT INTO lookup_options (
            tenant_id, category, code, label, description, is_active, display_order,
            created_at, updated_at
        )
        SELECT
            r.tenant_id,
            'workforce_roles',
            r.code,
            r.label,
            r.description,
            COALESCE(r.is_active, true),
            COALESCE(r.display_order, 0),
            NOW(),
            NOW()
        FROM lookup_options r
        WHERE r.category = 'roles'
          AND NOT EXISTS (
            SELECT 1 FROM lookup_options w
            WHERE w.category = 'workforce_roles'
              AND w.code = r.code
              AND w.tenant_id IS NOT DISTINCT FROM r.tenant_id
          )
        """
    )

    # Ensure default severity_levels exist for tenants that have none (global/null tenant).
    op.execute(
        """
        INSERT INTO lookup_options (
            tenant_id, category, code, label, is_active, display_order, created_at, updated_at
        )
        SELECT NULL, v.category, v.code, v.label, true, v.display_order, NOW(), NOW()
        FROM (
            VALUES
                ('severity_levels', 'low', 'Low', 1),
                ('severity_levels', 'medium', 'Medium', 2),
                ('severity_levels', 'high', 'High', 3),
                ('severity_levels', 'critical', 'Critical', 4)
        ) AS v(category, code, label, display_order)
        WHERE NOT EXISTS (
            SELECT 1 FROM lookup_options l
            WHERE l.category = 'severity_levels' AND l.code = v.code AND l.tenant_id IS NULL
        )
        """
    )


def downgrade() -> None:
    # Non-destructive: leave copied lookup rows in place (safe).
    pass
