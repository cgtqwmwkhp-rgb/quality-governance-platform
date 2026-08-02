"""Create the seven IMS unification tables (C-24).

Revision ID: 20260907_ims_unification
Revises: 20260906_doc_ctl_children
Create Date: 2026-09-07

``src/domain/models/ims_unification.py`` declares nine tables. Two of them
(``ims_requirements``, ``cross_standard_mappings``) were given a create migration
on 2026-04-07 by ``f6e5d4c3b2a1``, for the same reason as this one: the ORM
declared them and no migration built them, so a database promoted from the
migration chain answered ``ProgrammingError``. The other seven never got that
treatment and are still absent from every Alembic-built deployment.

Nothing reads them. That is the whole difference between this migration and
``20260906_doc_ctl_children``, which had to be preceded by disclosure work
because six of its seven tables had live readers returning 500. These seven are
declared, unmigrated and unqueried, so creating them changes no behaviour --
what it changes is that ``alembic check`` can compare them, which is why the
seven names come off ``_ALEMBIC_CHECK_EXCLUDED_TABLES`` in this PR.

Shape is taken from ``alembic.autogenerate`` against a database at the previous
head, so ``alembic check`` produces no operation for any of these tables once
they stop being excluded.

Additive and idempotent. Each table is skipped if it already exists, because
this migration runs on installations nobody has enumerated and a create is the
one operation that cannot be made safe by ordering alone. Unlike the seven
document-control tables, these seven were never enumerated in production -- the
Run 021 read covered document control only, and everything said about these
rests on the local ``alembic upgrade head`` reproduction
(``docs/ops/absent-table-disclosure.md`` §1). So a table already being there is
a real possibility, and skipping is what keeps that case from aborting a deploy
with ``DuplicateTableError``, as ``20260903_push_notif`` did.

The skip does not verify the shape of what it found. A pre-existing table with
the wrong columns is adopted, not reconciled -- the same trade
``20260906_doc_ctl_children`` made. It is recorded in the deploy log rather than
passed over in silence, so the one environment where it happens is identifiable.
Nothing reads these tables, so an adopted mis-shaped one breaks no surface
today; ``alembic check`` will report the column difference from the next run
onward, which is the point of taking them off the exclusion register.

Ordering note: ``20260308_tenant`` lists all seven and skipped every one of
them, having found no table to alter. The nullable ``tenant_id`` column and
``ix_<table>_tenant_id`` index it would have produced are therefore written here
directly, which is also what the models declare -- none of the seven is a TEN2
NOT NULL candidate.

Not in scope: row-level security. A table under FORCE RLS needs a dedicated
expand migration plus a matching entry in ``RLS_TABLES``
(``src/infrastructure/middleware/tenant_context.py``), and
``tests/integration/test_run026_rls_least_privilege_postgres.py`` fails on a
policy that is not registered there. All seven declare ``tenant_id`` nullable,
so they do not even meet the precondition the expand waves used. Creating them
here does not pre-empt that decision.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_ims_unification"
down_revision: Union[str, Sequence[str], None] = "20260906_doc_ctl_children"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Drop order is the reverse of create order, so foreign keys never dangle.
#: ``ims_control_requirement_mappings`` also references ``ims_requirements``,
#: which ``f6e5d4c3b2a1`` created unconditionally long before this revision.
TABLES_IN_DEPENDENCY_ORDER = (
    "ims_controls",
    "ims_control_requirement_mappings",
    "ims_objectives",
    "ims_process_maps",
    "management_reviews",
    "management_review_inputs",
    "unified_audit_plans",
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _create_ims_controls() -> None:
    op.create_table(
        "ims_controls",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("process_area", sa.String(length=100), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("standards_addressed", sa.JSON(), nullable=False),
        sa.Column("clauses_addressed", sa.JSON(), nullable=False),
        sa.Column("implementation_status", sa.String(length=50), nullable=False, server_default="implemented"),
        sa.Column("implementation_evidence", sa.Text(), nullable=True),
        sa.Column("effectiveness_rating", sa.String(length=50), nullable=False, server_default="effective"),
        sa.Column("last_effectiveness_review", sa.DateTime(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("procedure_reference", sa.String(length=255), nullable=True),
        sa.Column("document_links", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_ims_controls_tenant_id", "ims_controls", ["tenant_id"])


def _create_ims_control_requirement_mappings() -> None:
    op.create_table(
        "ims_control_requirement_mappings",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("coverage_level", sa.String(length=50), nullable=False, server_default="full"),
        sa.Column("coverage_percentage", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("coverage_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["control_id"], ["ims_controls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["ims_requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ims_control_requirement_mappings_tenant_id",
        "ims_control_requirement_mappings",
        ["tenant_id"],
    )


def _create_ims_objectives() -> None:
    op.create_table(
        "ims_objectives",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("objective_type", sa.String(length=50), nullable=False),
        sa.Column("standards_addressed", sa.JSON(), nullable=False),
        sa.Column("policy_alignment", sa.Text(), nullable=True),
        sa.Column("specific", sa.Text(), nullable=True),
        sa.Column("measurable_indicator", sa.String(length=255), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=50), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=False),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="on_track"),
        sa.Column("responsible_id", sa.Integer(), nullable=True),
        sa.Column("responsible_name", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("resources_required", sa.Text(), nullable=True),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("action_plan", sa.JSON(), nullable=True),
        sa.Column("last_review_date", sa.DateTime(), nullable=True),
        sa.Column("next_review_date", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["responsible_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_ims_objectives_tenant_id", "ims_objectives", ["tenant_id"])


def _create_ims_process_maps() -> None:
    op.create_table(
        "ims_process_maps",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("process_id", sa.String(length=50), nullable=False),
        sa.Column("process_name", sa.String(length=255), nullable=False),
        sa.Column("process_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("suppliers", sa.JSON(), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("outputs", sa.JSON(), nullable=True),
        sa.Column("customers", sa.JSON(), nullable=True),
        sa.Column("relevant_standards", sa.JSON(), nullable=False),
        sa.Column("relevant_clauses", sa.JSON(), nullable=False),
        sa.Column("process_owner_id", sa.Integer(), nullable=True),
        sa.Column("process_owner_name", sa.String(length=255), nullable=True),
        sa.Column("kpis", sa.JSON(), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=True),
        sa.Column("procedure_references", sa.JSON(), nullable=True),
        sa.Column("work_instructions", sa.JSON(), nullable=True),
        sa.Column("forms_records", sa.JSON(), nullable=True),
        sa.Column("associated_risks", sa.JSON(), nullable=True),
        sa.Column("opportunities", sa.JSON(), nullable=True),
        sa.Column("upstream_processes", sa.JSON(), nullable=True),
        sa.Column("downstream_processes", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["process_owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("process_id"),
    )
    op.create_index("ix_ims_process_maps_tenant_id", "ims_process_maps", ["tenant_id"])


def _create_management_reviews() -> None:
    op.create_table(
        "management_reviews",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("standards_reviewed", sa.JSON(), nullable=False),
        sa.Column("review_period_start", sa.DateTime(), nullable=False),
        sa.Column("review_period_end", sa.DateTime(), nullable=False),
        sa.Column("meeting_date", sa.DateTime(), nullable=False),
        sa.Column("meeting_location", sa.String(length=255), nullable=True),
        sa.Column("attendees", sa.JSON(), nullable=True),
        sa.Column("chair_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="planned"),
        sa.Column("outputs", sa.JSON(), nullable=True),
        sa.Column("decisions", sa.JSON(), nullable=True),
        sa.Column("action_items", sa.JSON(), nullable=True),
        sa.Column("ims_effectiveness", sa.String(length=50), nullable=True),
        sa.Column("policy_adequacy", sa.String(length=50), nullable=True),
        sa.Column("objectives_achievement", sa.String(length=50), nullable=True),
        sa.Column("resource_adequacy", sa.String(length=50), nullable=True),
        sa.Column("continual_improvement_opportunities", sa.JSON(), nullable=True),
        sa.Column("changes_needed", sa.JSON(), nullable=True),
        sa.Column("minutes_link", sa.String(length=500), nullable=True),
        sa.Column("next_review_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["chair_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_management_reviews_tenant_id", "management_reviews", ["tenant_id"])


def _create_management_review_inputs() -> None:
    op.create_table(
        "management_review_inputs",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("subcategory", sa.String(length=100), nullable=True),
        sa.Column("source_standards", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("current_value", sa.String(length=255), nullable=True),
        sa.Column("previous_value", sa.String(length=255), nullable=True),
        sa.Column("trend", sa.String(length=50), nullable=True),
        sa.Column("target_value", sa.String(length=255), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("risk_implications", sa.Text(), nullable=True),
        sa.Column("data_period_start", sa.DateTime(), nullable=True),
        sa.Column("data_period_end", sa.DateTime(), nullable=True),
        sa.Column("data_source", sa.String(length=255), nullable=True),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("prepared_by", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["prepared_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["management_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_management_review_inputs_tenant_id", "management_review_inputs", ["tenant_id"])


def _create_unified_audit_plans() -> None:
    op.create_table(
        "unified_audit_plans",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("standards_in_scope", sa.JSON(), nullable=False),
        sa.Column("clauses_in_scope", sa.JSON(), nullable=False),
        sa.Column("processes_in_scope", sa.JSON(), nullable=True),
        sa.Column("departments_in_scope", sa.JSON(), nullable=True),
        sa.Column("audit_type", sa.String(length=50), nullable=False),
        sa.Column("audit_cycle", sa.String(length=50), nullable=False, server_default="annual"),
        sa.Column("planned_start_date", sa.DateTime(), nullable=False),
        sa.Column("planned_end_date", sa.DateTime(), nullable=False),
        sa.Column("actual_start_date", sa.DateTime(), nullable=True),
        sa.Column("actual_end_date", sa.DateTime(), nullable=True),
        sa.Column("lead_auditor_id", sa.Integer(), nullable=True),
        sa.Column("lead_auditor_name", sa.String(length=255), nullable=True),
        sa.Column("audit_team", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="planned"),
        sa.Column("completion_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("major_nc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minor_nc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opportunities_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_link", sa.String(length=500), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["lead_auditor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_unified_audit_plans_tenant_id", "unified_audit_plans", ["tenant_id"])


_CREATORS = {
    "ims_controls": _create_ims_controls,
    "ims_control_requirement_mappings": _create_ims_control_requirement_mappings,
    "ims_objectives": _create_ims_objectives,
    "ims_process_maps": _create_ims_process_maps,
    "management_reviews": _create_management_reviews,
    "management_review_inputs": _create_management_review_inputs,
    "unified_audit_plans": _create_unified_audit_plans,
}


def upgrade() -> None:
    for table_name in TABLES_IN_DEPENDENCY_ORDER:
        if _table_exists(table_name):
            print(f"20260907_ims_unification: adopted the existing {table_name!r} unverified")
            continue
        _CREATORS[table_name]()


def downgrade() -> None:
    for table_name in reversed(TABLES_IN_DEPENDENCY_ORDER):
        if _table_exists(table_name):
            op.drop_table(table_name)
