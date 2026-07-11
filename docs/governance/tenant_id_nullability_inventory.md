# Tenant ID nullability inventory (C-01 Phase 1)

Generated from public SQLAlchemy models in `src.domain.models`.

## Summary

| Category | Count |
| --- | ---: |
| Required `tenant_id` (`nullable=False`) | 30 |
| Owned nullable `tenant_id` | 68 |
| Catalog/global nullable `tenant_id` | 19 |
| No `tenant_id` column | 6 |
| **Nullable total** | **102** |

## Phase 1 decision

Mass `NOT NULL` across ~170 tables is **deferred**. Live NULL-row risk is
unknown without environment-specific counts, and document-control already
uses a phased backfill pattern (`docs/data/document-control-tenant-backfill.md`).

This phase lands:

1. This inventory + grandfather baseline for owned nullable tables.
2. CI lint forbidding **new** owned entities with nullable `tenant_id`.
3. Explicit catalog/global exception list.

## Phase 2 progress

| Table | Status | Notes |
| --- | --- | --- |
| `audit_findings` | **Done (incremental)** | Fail-safe backfill from `audit_runs` + conditional `NOT NULL` (`20260710_af_tenant_nn`). ORM `nullable=False`. See `docs/data/audit-findings-tenant-backfill.md`. |
| `incident_actions` | **Done (incremental)** | Fail-safe backfill from `incidents` + conditional `NOT NULL` (`20260710_ia_tenant_nn`). ORM `nullable=False`. See `docs/data/incident-actions-tenant-backfill.md`. |
| `complaint_actions` | **Done (incremental)** | Fail-safe backfill from `complaints` + conditional `NOT NULL` (`20260710_ca_tenant_nn`). ORM `nullable=False`. See `docs/data/complaint-actions-tenant-backfill.md`. |
| `audit_runs` | **Done (incremental)** | Fail-safe backfill from `audit_templates` + conditional `NOT NULL` (`20260710_ar_tenant_nn`). ORM `nullable=False`. See `docs/data/audit-runs-tenant-backfill.md`. |
| `rta_actions` | **Done (incremental)** | Fail-safe backfill from `road_traffic_collisions` + conditional `NOT NULL` (`20260710_rta_act_nn`). ORM `nullable=False`. See `docs/data/rta-actions-tenant-backfill.md`. |
| `capa_actions` | **Done (incremental)** | Fail-safe backfill from `users` (creator) + conditional `NOT NULL` (`20260710_capa_act_nn`). ORM `nullable=False`. See `docs/data/capa-actions-tenant-backfill.md`. |
| `investigation_actions` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_act_nn`). ORM `nullable=False`. See `docs/data/investigation-actions-tenant-backfill.md`. |
| `investigation_comments` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_cmt_nn`). ORM `nullable=False`. See `docs/data/investigation-comments-tenant-backfill.md`. |
| `investigation_revision_events` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_rev_evt_nn`). ORM `nullable=False`. See `docs/data/investigation-revision-events-tenant-backfill.md`. |
| `investigation_runs` | **Done (incremental)** | Fail-safe backfill from `investigation_templates` + conditional `NOT NULL` (`20260710_ir_tenant_nn`). ORM `nullable=False`. See `docs/data/investigation-runs-tenant-backfill.md`. |
| `investigation_customer_packs` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_pack_nn`). ORM `nullable=False`. See `docs/data/investigation-customer-packs-tenant-backfill.md`. |
| `road_traffic_collisions` | Done (fail-safe) | Parent core TEN2 — creator/reporter backfill; NOT NULL only when residual NULLs=0. |
| `risk_assessments` | Done (fail-safe) | Child of `risks` via `risk_id`; NOT NULL only when residual NULLs=0. |
| `risks_v2` | Done (fail-safe) | Parent core TEN2 — creator/owner backfill; NOT NULL only when residual NULLs=0. |
| `bow_tie_elements` | Done (fail-safe) | Child of `risks_v2` via `risk_id`; NOT NULL only when residual NULLs=0. |
| `risk_control_mappings` | Done (fail-safe) | Child of `risks_v2` via `risk_id`; NOT NULL only when residual NULLs=0. |
| `key_risk_indicators` | Done (fail-safe) | Child of `risks_v2` via `risk_id`; NOT NULL only when residual NULLs=0. |
| `risk_assessment_history` | Done (fail-safe) | Child of `risks_v2` via `risk_id`; NOT NULL only when residual NULLs=0. |
| `enterprise_risk_controls` | Done (fail-safe) | Owner backfill from `users` via `control_owner_id`; NOT NULL only when residual NULLs=0. |
| `policy_versions` | Done (fail-safe) | Child of `policies` via `policy_id`; NOT NULL only when residual NULLs=0. |
| `controlled_document_versions` | Done (fail-safe) | Child of `controlled_documents` via `document_id`; NOT NULL only when residual NULLs=0. |
| `controlled_documents` | Done (fail-safe) | Parent core TEN2 — author/owner user backfill; NOT NULL only when residual NULLs=0. |
| `policies` | Done (fail-safe) | Parent core TEN2 — creator/owner user backfill; NOT NULL only when residual NULLs=0. |
| `documents` | Done (fail-safe) | Parent core TEN2 — creator/reviewer user backfill; NOT NULL only when residual NULLs=0. |
| `document_versions` | Done (fail-safe) | Child of `documents` via `document_id`; NOT NULL only when residual NULLs=0. |
| `obsolete_document_records` | Done (fail-safe) | Child of `controlled_documents` via `document_id`; NOT NULL only when residual NULLs=0. |
| `document_access_logs` | Done (fail-safe) | Child of `controlled_documents` via `document_id`; NOT NULL only when residual NULLs=0. |
| `document_annotations` | Done (fail-safe) | Child of `documents` via `document_id`; NOT NULL only when residual NULLs=0. |

## Highest-risk Phase 2 candidates (backfill + NOT NULL when safe)

Do **not** enforce `NOT NULL` until NULL counts are zero in every environment
and ownership attribution is approved (no silent `tenant_id=1` backfill).

| Table | Model |
| --- | --- |
| `risk_assessments` | `RiskAssessment` |
| `risks_v2` | `EnterpriseRisk` |
## Required `tenant_id`

| Table | Model |
| --- | --- |
| `audit_findings` | `AuditFinding` |
| `audit_runs` | `AuditRun` |
| `capa_actions` | `CAPAAction` |
| `complaint_actions` | `ComplaintAction` |
| `complaints` | `Complaint` |
| `compliance_evidence_links` | `ComplianceEvidenceLink` |
| `copilot_feedback` | `CopilotFeedback` |
| `copilot_sessions` | `CopilotSession` |
| `external_audit_import_drafts` | `ExternalAuditDraft` |
| `external_audit_import_jobs` | `ExternalAuditImportJob` |
| `incident_actions` | `IncidentAction` |
| `incidents` | `Incident` |
| `investigation_comments` | `InvestigationComment` |
| `investigation_customer_packs` | `InvestigationCustomerPack` |
| `investigation_revision_events` | `InvestigationRevisionEvent` |
| `investigation_runs` | `InvestigationRun` |
| `risks` | `Risk` |
| `road_traffic_collisions` | `RoadTrafficCollision` |
| `rta_actions` | `RTAAction` |
| `signature_audit_logs` | `SignatureAuditLog` |
| `signature_requests` | `SignatureRequest` |
| `signature_templates` | `SignatureTemplate` |
| `signatures` | `Signature` |
| `tenant_invitations` | `TenantInvitation` |
| `tenant_users` | `TenantUser` |

## Owned nullable `tenant_id` (grandfathered)

| Table | Model |
| --- | --- |
| `access_control_records` | `AccessControlRecord` |
| `action_owner_notes` | `ActionOwnerNote` |
| `assessment_responses` | `AssessmentResponse` |
| `assessment_runs` | `AssessmentRun` |
| `assets` | `Asset` |
| `benchmark_data` | `BenchmarkData` |
| `business_continuity_plans` | `BusinessContinuityPlan` |
| `carbon_evidence` | `CarbonEvidence` |
| `carbon_improvement_action` | `ImprovementAction` |
| `carbon_reporting_year` | `CarbonReportingYear` |
| `competency_records` | `CompetencyRecord` |
| `competency_requirements` | `CompetencyRequirement` |
| `contracts` | `Contract` |
| `copilot_actions` | `CopilotAction` |
| `copilot_knowledge` | `CopilotKnowledge` |
| `copilot_messages` | `CopilotMessage` |
| `cost_records` | `CostRecord` |
| `dashboard_widgets` | `DashboardWidget` |
| `dashboards` | `Dashboard` |
| `data_quality_assessment` | `DataQualityAssessment` |
| `document_annotations` | `DocumentAnnotation` |
| `document_approval_actions` | `DocumentApprovalAction` |
| `document_approval_instances` | `DocumentApprovalInstance` |
| `document_approval_workflows` | `DocumentApprovalWorkflow` |
| `document_chunks` | `DocumentChunk` |
| `document_distributions` | `DocumentDistribution` |
| `document_search_logs` | `DocumentSearchLog` |
| `document_training_links` | `DocumentTrainingLink` |
| `driver_acknowledgements` | `DriverAcknowledgement` |
| `driver_profiles` | `DriverProfile` |
| `emission_source` | `EmissionSource` |
| `engineers` | `Engineer` |
| `evidence_assets` | `EvidenceAsset` |
| `fleet_emission_record` | `FleetEmissionRecord` |
| `ims_control_requirement_mappings` | `IMSControlRequirementMapping` |
| `ims_controls` | `IMSControl` |
| `ims_objectives` | `IMSObjective` |
| `ims_process_maps` | `IMSProcessMap` |
| `ims_requirements` | `IMSRequirement` |
| `index_jobs` | `IndexJob` |
| `induction_responses` | `InductionResponse` |
| `induction_runs` | `InductionRun` |
| `information_assets` | `InformationAsset` |
| `information_security_risks` | `InformationSecurityRisk` |
| `iso27001_controls` | `ISO27001Control` |
| `loler_defects` | `LOLERDefect` |
| `loler_examinations` | `LOLERExamination` |
| `management_review_inputs` | `ManagementReviewInput` |
| `management_reviews` | `ManagementReview` |
| `onboarding_checklists` | `OnboardingChecklist` |
| `risk_appetite_statements` | `RiskAppetiteStatement` |
| `risk_controls` | `OperationalRiskControl` |
| `roi_investments` | `ROIInvestment` |
| `saved_reports` | `SavedReport` |
| `scope3_category_data` | `Scope3CategoryData` |
| `security_incidents` | `SecurityIncident` |
| `signature_request_signers` | `SignatureRequestSigner` |
| `soa_control_entries` | `SoAControlEntry` |
| `statement_of_applicability` | `StatementOfApplicability` |
| `supplier_emission_data` | `SupplierEmissionData` |
| `supplier_security_assessments` | `SupplierSecurityAssessment` |
| `unified_audit_plans` | `UnifiedAuditPlan` |
| `users` | `User` |
| `utility_meter_reading` | `UtilityMeterReading` |
| `uvdb_audit` | `UVDBAudit` |
| `uvdb_audit_response` | `UVDBAuditResponse` |
| `uvdb_kpi_record` | `UVDBKPIRecord` |
| `vehicle_registry` | `VehicleRegistry` |
## Catalog / global exceptions (nullable allowed)

| Table | Model |
| --- | --- |
| `asset_types` | `AssetType` |
| `audit_templates` | `AuditTemplate` |
| `clauses` | `Clause` |
| `controls` | `Control` |
| `cross_standard_mappings` | `CrossStandardMapping` |
| `form_fields` | `FormField` |
| `form_steps` | `FormStep` |
| `form_templates` | `FormTemplate` |
| `investigation_templates` | `InvestigationTemplate` |
| `lookup_options` | `LookupOption` |
| `planet_mark_iso14001_mapping` | `ISO14001CrossMapping` |
| `roles` | `Role` |
| `standards` | `Standard` |
| `system_settings` | `SystemSetting` |
| `template_asset_types` | `TemplateAssetType` |
| `template_versions` | `TemplateVersion` |
| `uvdb_iso_cross_mapping` | `UVDBISOCrossMapping` |
| `uvdb_question` | `UVDBQuestion` |
| `uvdb_section` | `UVDBSection` |

## No `tenant_id` column

| Table | Model |
| --- | --- |
| `audit_questions` | `AuditQuestion` |
| `audit_responses` | `AuditResponse` |
| `audit_sections` | `AuditSection` |
| `feature_flags` | `FeatureFlag` |
| `tenants` | `Tenant` |
| `token_blacklist` | `TokenBlacklist` |
