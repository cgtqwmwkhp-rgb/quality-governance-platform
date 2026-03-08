"""Add tenant_id column to all models for complete multi-tenant isolation.

Revision ID: 20260308_tenant
Revises: 20260306_rc_idx
Create Date: 2026-03-08

Uses ADD COLUMN IF NOT EXISTS so tables that already have tenant_id
are safely skipped. Sets DEFAULT 1 for existing rows.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260308_tenant"
down_revision: Union[str, None] = "20260306_rc_idx"
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


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            f"tenant_id INTEGER REFERENCES tenants(id)"
        )
        op.execute(
            f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id "
            f"ON {table} (tenant_id)"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_tenant_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id")
