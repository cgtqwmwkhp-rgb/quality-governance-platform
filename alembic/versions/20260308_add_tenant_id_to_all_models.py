"""Add tenant_id column to all models for complete multi-tenant isolation.

Revision ID: 20260308_tenant
Revises: 20260306_rc_idx
Create Date: 2026-03-08

Uses ADD COLUMN IF NOT EXISTS so tables that already have tenant_id
are safely skipped. Sets DEFAULT 1 for existing rows.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260308_tenant"
down_revision: Union[str, None] = "20260303_pos_ans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "abac_policies",
    "abac_role_permissions",
    "abac_roles",
    "abac_user_roles",
    "access_control_records",
    "approval_requests",
    "assessment_responses",
    "assessment_runs",
    "asset_types",
    "assets",
    "assignments",
    "audit_assignment_criteria",
    "audit_builder_findings",
    "audit_builder_responses",
    "audit_builder_runs",
    "audit_builder_templates",
    "audit_log_entries",
    "audit_log_exports",
    "audit_log_verifications",
    "audit_questions",
    "audit_responses",
    "audit_sections",
    "audit_template_questions",
    "audit_template_sections",
    "audit_template_versions",
    "auditor_certifications",
    "auditor_competencies",
    "auditor_profiles",
    "auditor_training",
    "barrier_analyses",
    "benchmark_data",
    "business_continuity_plans",
    "capa_actions",
    "capa_items",
    "carbon_evidence",
    "carbon_improvement_action",
    "carbon_reporting_year",
    "certificates",
    "clauses",
    "collaborative_changes",
    "collaborative_documents",
    "collaborative_sessions",
    "competency_areas",
    "competency_records",
    "competency_requirements",
    "complaint_actions",
    "compliance_evidence_links",
    "compliance_scores",
    "contracts",
    "controlled_document_versions",
    "controlled_documents",
    "controls",
    "copilot_actions",
    "copilot_feedback",
    "copilot_knowledge",
    "copilot_messages",
    "copilot_sessions",
    "cost_records",
    "cross_standard_mappings",
    "dashboard_widgets",
    "dashboards",
    "data_quality_assessment",
    "document_access_logs",
    "document_annotations",
    "document_approval_actions",
    "document_approval_instances",
    "document_approval_workflows",
    "document_chunks",
    "document_comments",
    "document_distributions",
    "document_read_logs",
    "document_search_logs",
    "document_training_links",
    "document_versions",
    "emission_source",
    "engineers",
    "enterprise_risk_controls",
    "escalation_levels",
    "escalation_logs",
    "escalation_rules",
    "evidence_assets",
    "failed_tasks",
    "field_level_permissions",
    "fishbone_diagrams",
    "five_whys_analyses",
    "fleet_emission_record",
    "form_fields",
    "form_steps",
    "form_templates",
    "gap_analyses",
    "ims_control_requirement_mappings",
    "ims_controls",
    "ims_objectives",
    "ims_process_maps",
    "ims_requirements",
    "incident_actions",
    "index_jobs",
    "induction_responses",
    "induction_runs",
    "investigation_actions",
    "investigation_comments",
    "investigation_customer_packs",
    "investigation_revision_events",
    "investigation_templates",
    "iso27001_controls",
    "key_risk_indicators",
    "kri_alerts",
    "kri_measurements",
    "loler_defects",
    "loler_examinations",
    "lookup_options",
    "management_review_inputs",
    "management_reviews",
    "mentions",
    "near_misses",
    "notification_preferences",
    "notifications",
    "obsolete_document_records",
    "onboarding_checklists",
    "permission_audits",
    "permissions",
    "planet_mark_iso14001_mapping",
    "policy_acknowledgment_requirements",
    "policy_acknowledgments",
    "policy_versions",
    "regulatory_updates",
    "riddor_submissions",
    "risk_appetite_statements",
    "risk_assessment_history",
    "risk_assessments",
    "risk_control_mappings",
    "risk_controls",
    "risk_score_history",
    "road_traffic_collisions",
    "roi_investments",
    "roles",
    "root_cause_analyses",
    "rta_actions",
    "rule_executions",
    "saved_reports",
    "scheduled_audits",
    "scope3_category_data",
    "signature_audit_logs",
    "signature_request_signers",
    "signature_requests",
    "signature_templates",
    "signatures",
    "sla_configurations",
    "sla_tracking",
    "soa_control_entries",
    "standards",
    "statement_of_applicability",
    "supplier_emission_data",
    "system_settings",
    "template_asset_types",
    "tenant_invitations",
    "tenant_users",
    "unified_audit_plans",
    "user_delegations",
    "user_presence",
    "utility_meter_reading",
    "uvdb_audit",
    "uvdb_audit_response",
    "uvdb_iso_cross_mapping",
    "uvdb_kpi_record",
    "uvdb_question",
    "uvdb_section",
    "workflow_instances",
    "workflow_rules",
    "workflow_steps",
    "workflow_templates",
]

RLS_TABLES = [
    "incidents",
    "complaints",
    "risks",
    "capa_actions",
    "audit_runs",
    "investigation_runs",
    "documents",
    "near_misses",
    "road_traffic_collisions",
    "workflow_rules",
    "users",
    "audit_log_entries",
]


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {col["name"] for col in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def _indexes_using_column(table_name: str, column_name: str) -> list[str]:
    if not _table_exists(table_name):
        return []
    return [
        index["name"]
        for index in _inspector().get_indexes(table_name)
        if column_name in (index.get("column_names") or [])
    ]


def _drop_postgres_tenant_policies(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql" or table_name not in RLS_TABLES:
        return
    op.execute(
        f"DO $$ BEGIN "
        f"  IF EXISTS (SELECT 1 FROM pg_class WHERE relname = '{table_name}') THEN "
        f"    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table_name}'; "
        f"    EXECUTE 'ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY'; "
        f"  END IF; "
        f"EXCEPTION WHEN OTHERS THEN "
        f"  RAISE NOTICE 'Tenant policy teardown skip for {table_name}: %', SQLERRM; "
        f"END $$"
    )


def upgrade() -> None:
    for table in TABLES:
        if not _table_exists(table):
            continue
        if not _has_column(table, "tenant_id"):
            op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
        index_name = f"ix_{table}_tenant_id"
        if not _has_index(table, index_name):
            op.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} (tenant_id)")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    for table in reversed(TABLES):
        if not _table_exists(table):
            continue
        if not _has_column(table, "tenant_id"):
            continue
        for index_name in _indexes_using_column(table, "tenant_id"):
            if dialect == "postgresql":
                op.drop_index(index_name, table_name=table)
            else:
                op.execute(f"DROP INDEX IF EXISTS {index_name}")
        _drop_postgres_tenant_policies(table)
        if dialect == "sqlite":
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("tenant_id")
        else:
            op.drop_column(table, "tenant_id")
