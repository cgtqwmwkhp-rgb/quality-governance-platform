"""Location coverage quotas + coverage-quorum catalogue templates (CB-PR5).

Revision ID: 20260901_comp_cov
Revises: 20260901_comp_bind

Coverage is a location duty (n of m appointed people), never a per-person
compliance-schedule row — ADR-0020 stays. The catalogue upsert is re-run so the
three new location-duty templates land from ``catalogue.json``; it is the same
idempotent upsert Wave 0 uses, not a second seed.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_comp_cov"
down_revision: Union[str, Sequence[str], None] = "20260901_comp_bind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("competence_coverage_quotas"):
        op.create_table(
            "competence_coverage_quotas",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("role_key", sa.String(length=40), nullable=False),
            sa.Column("required_n", sa.Integer(), nullable=False),
            sa.Column("template_key", sa.String(length=80), nullable=False),
            sa.Column("match_department", sa.String(length=200), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id",
                "location_id",
                "role_key",
                name="uq_competence_coverage_quotas_location_role",
            ),
            sa.CheckConstraint("required_n >= 1", name="ck_competence_coverage_quotas_required_n"),
            sa.CheckConstraint(
                "role_key IN ('first_aider', 'fire_marshal', 'mhfa')",
                name="ck_competence_coverage_quotas_role_key",
            ),
        )
        op.create_index(
            "ix_competence_coverage_quotas_tenant_id",
            "competence_coverage_quotas",
            ["tenant_id"],
        )

    _upsert_catalogue_templates()


def _upsert_catalogue_templates() -> None:
    """Re-run the Wave 0 catalogue upsert so new template_keys land.

    ``catalogue.json`` is the source of truth and the upsert is keyed on
    ``template_key``, so this adds the three coverage-quorum rows and rewrites
    nothing an operator owns. Skipped when the table does not exist yet, which
    only happens if Compliance Schedule Wave 0 has not run.
    """
    if not _has_table("compliance_requirement_templates"):
        logger.info("%s: compliance_requirement_templates absent — skipping catalogue upsert", revision)
        return
    from src.domain.data.compliance_schedule_catalogue import upsert_compliance_templates

    count = upsert_compliance_templates(op.get_bind())
    logger.info("%s: upserted %d compliance requirement templates", revision, count)


def downgrade() -> None:
    # The catalogue rows are left in place: an operator may already have
    # activated a coverage obligation from one, and dropping the template would
    # orphan a live requirement. Only the quota table is removed.
    if _has_table("competence_coverage_quotas"):
        op.drop_index(
            "ix_competence_coverage_quotas_tenant_id",
            table_name="competence_coverage_quotas",
        )
        op.drop_table("competence_coverage_quotas")
