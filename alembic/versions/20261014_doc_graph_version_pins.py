"""Doc Graph P0: CEL + campaign library version pins.

Revision ID: 20261014_doc_graph_pins
Revises: 20261012_rls_sso_prov
Create Date: 2026-10-14

Pins evidence links and acknowledgement campaigns to a concrete library
``document_versions`` row so Doc Graph inheritance / impact cannot silently
inflate coverage or re-ack against a moving tip (ADR-0021 P0).

Also adds nullable ``standard_edition`` on CEL so clause catalogue edition can
be recorded without inventing document_edges.

Conflict note
-------------
Sibling branches may land ``20261013_cs_reg_link`` and/or
``20261013_cs_fra_ocr`` also revising ``20261012_rls_sso_prov``. This revision
deliberately uses ``20261014_*`` to avoid colliding revision *ids*; merge to
main will need an Alembic merge revision across multiple heads.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_doc_graph_pins"
down_revision: Union[str, Sequence[str], None] = "20261012_rls_sso_prov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "compliance_evidence_links",
        sa.Column("document_version_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "compliance_evidence_links",
        sa.Column("standard_edition", sa.String(length=100), nullable=True),
    )
    op.create_foreign_key(
        "fk_cel_document_version_id",
        "compliance_evidence_links",
        "document_versions",
        ["document_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_cel_document_version_id",
        "compliance_evidence_links",
        ["document_version_id"],
    )

    op.add_column(
        "document_campaigns",
        sa.Column("document_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_campaigns_document_version_id",
        "document_campaigns",
        "document_versions",
        ["document_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_campaigns_document_version_id",
        "document_campaigns",
        ["document_version_id"],
    )

    op.add_column(
        "campaign_assignments",
        sa.Column("acknowledged_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_campaign_assignments_acknowledged_version_id",
        "campaign_assignments",
        "document_versions",
        ["acknowledged_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_campaign_assignments_acknowledged_version_id",
        "campaign_assignments",
        ["acknowledged_version_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Best-effort tip backfill: published preferred over approved; newest tip wins.
    op.execute(
        sa.text(
            """
            WITH tip AS (
                SELECT DISTINCT ON (document_id, tenant_id)
                    id,
                    document_id,
                    tenant_id
                FROM document_versions
                WHERE status IN ('published', 'approved')
                ORDER BY
                    document_id,
                    tenant_id,
                    CASE status WHEN 'published' THEN 0 ELSE 1 END,
                    published_at DESC NULLS LAST,
                    id DESC
            )
            UPDATE compliance_evidence_links AS cel
            SET document_version_id = tip.id
            FROM tip
            WHERE cel.document_version_id IS NULL
              AND cel.entity_type = 'document'
              AND cel.entity_id ~ '^[0-9]+$'
              AND tip.document_id = cel.entity_id::integer
              AND tip.tenant_id = cel.tenant_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH tip AS (
                SELECT DISTINCT ON (document_id, tenant_id)
                    id,
                    document_id,
                    tenant_id
                FROM document_versions
                WHERE status IN ('published', 'approved')
                ORDER BY
                    document_id,
                    tenant_id,
                    CASE status WHEN 'published' THEN 0 ELSE 1 END,
                    published_at DESC NULLS LAST,
                    id DESC
            )
            UPDATE document_campaigns AS dc
            SET document_version_id = tip.id
            FROM tip
            WHERE dc.document_version_id IS NULL
              AND tip.document_id = dc.document_id
              AND tip.tenant_id = dc.tenant_id
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_assignments_acknowledged_version_id",
        table_name="campaign_assignments",
    )
    op.drop_constraint(
        "fk_campaign_assignments_acknowledged_version_id",
        "campaign_assignments",
        type_="foreignkey",
    )
    op.drop_column("campaign_assignments", "acknowledged_version_id")

    op.drop_index(
        "ix_document_campaigns_document_version_id",
        table_name="document_campaigns",
    )
    op.drop_constraint(
        "fk_document_campaigns_document_version_id",
        "document_campaigns",
        type_="foreignkey",
    )
    op.drop_column("document_campaigns", "document_version_id")

    op.drop_index("ix_cel_document_version_id", table_name="compliance_evidence_links")
    op.drop_constraint(
        "fk_cel_document_version_id",
        "compliance_evidence_links",
        type_="foreignkey",
    )
    op.drop_column("compliance_evidence_links", "standard_edition")
    op.drop_column("compliance_evidence_links", "document_version_id")
