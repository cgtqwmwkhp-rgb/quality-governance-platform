# Tenant ID nullability inventory (C-01 Phase 1)

Generated from public SQLAlchemy models in `src.domain.models`.

## Summary

| Category | Count |
| --- | ---: |
| Required `tenant_id` (`nullable=False`) | 10 |
| Owned nullable `tenant_id` | 98 |
| Catalog/global nullable `tenant_id` | 19 |
| No `tenant_id` column | 6 |
| **Nullable total** | **117** |

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
| `audit_runs` | Deferred | Parent may still be NULL — do not invent `tenant_id=1`. |
| `incidents` / `incident_actions` / `risks` / `risks_v2` / `risk_assessments` / `complaints` | Deferred | Out of scope for the findings-only revision. |

## Highest-risk Phase 2 candidates (backfill + NOT NULL when safe)

Do **not** enforce `NOT NULL` until NULL counts are zero in every environment
and ownership attribution is approved (no silent `tenant_id=1` backfill).

| Table | Model |
| --- | --- |
| `audit_runs` | `AuditRun` |
| `complaints` | `Complaint` |
| `incident_actions` | `IncidentAction` |
| `incidents` | `Incident` |
| `risk_assessments` | `RiskAssessment` |
| `risks` | `Risk` |
| `risks_v2` | `EnterpriseRisk` |

## Required `tenant_id`

| Table | Model |
| --- | --- |
| `audit_findings` | `AuditFinding` |
| `compliance_evidence_links` | `ComplianceEvidenceLink` |
| `copilot_feedback` | `CopilotFeedback` |
| `copilot_sessions` | `CopilotSession` |
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
| `audit_runs` | `AuditRun` |
| `benchmark_data` | `BenchmarkData` |
| `bow_tie_elements` | `BowTieElement` |
| `business_continuity_plans` | `BusinessContinuityPlan` |
| `capa_actions` | `CAPAAction` |
| `carbon_evidence` | `CarbonEvidence` |
| `carbon_improvement_action` | `ImprovementAction` |
| `carbon_reporting_year` | `CarbonReportingYear` |
| `competency_records` | `CompetencyRecord` |
| `competency_requirements` | `CompetencyRequirement` |
| `complaint_actions` | `ComplaintAction` |
| `complaints` | `Complaint` |
| `contracts` | `Contract` |
| `controlled_document_versions` | `ControlledDocumentVersion` |
| `controlled_documents` | `ControlledDocument` |
| `copilot_actions` | `CopilotAction` |
| `copilot_knowledge` | `CopilotKnowledge` |
| `copilot_messages` | `CopilotMessage` |
| `cost_records` | `CostRecord` |
| `dashboard_widgets` | `DashboardWidget` |
| `dashboards` | `Dashboard` |
| `data_quality_assessment` | `DataQualityAssessment` |
| `document_access_logs` | `DocumentAccessLog` |
| `document_annotations` | `DocumentAnnotation` |
| `document_approval_actions` | `DocumentApprovalAction` |
| `document_approval_instances` | `DocumentApprovalInstance` |
| `document_approval_workflows` | `DocumentApprovalWorkflow` |
| `document_chunks` | `DocumentChunk` |
| `document_distributions` | `DocumentDistribution` |
| `document_search_logs` | `DocumentSearchLog` |
| `document_training_links` | `DocumentTrainingLink` |
| `document_versions` | `DocumentVersion` |
| `documents` | `Document` |
| `driver_acknowledgements` | `DriverAcknowledgement` |
| `driver_profiles` | `DriverProfile` |
| `emission_source` | `EmissionSource` |
| `engineers` | `Engineer` |
| `enterprise_risk_controls` | `EnterpriseRiskControl` |
| `evidence_assets` | `EvidenceAsset` |
| `external_audit_import_drafts` | `ExternalAuditDraft` |
| `external_audit_import_jobs` | `ExternalAuditImportJob` |
| `fleet_emission_record` | `FleetEmissionRecord` |
| `ims_control_requirement_mappings` | `IMSControlRequirementMapping` |
| `ims_controls` | `IMSControl` |
| `ims_objectives` | `IMSObjective` |
| `ims_process_maps` | `IMSProcessMap` |
| `ims_requirements` | `IMSRequirement` |
| `incident_actions` | `IncidentAction` |
| `incidents` | `Incident` |
| `index_jobs` | `IndexJob` |
| `induction_responses` | `InductionResponse` |
| `induction_runs` | `InductionRun` |
| `information_assets` | `InformationAsset` |
| `information_security_risks` | `InformationSecurityRisk` |
| `investigation_comments` | `InvestigationComment` |
| `investigation_customer_packs` | `InvestigationCustomerPack` |
| `investigation_revision_events` | `InvestigationRevisionEvent` |
| `investigation_runs` | `InvestigationRun` |
| `iso27001_controls` | `ISO27001Control` |
| `key_risk_indicators` | `EnterpriseKeyRiskIndicator` |
| `loler_defects` | `LOLERDefect` |
| `loler_examinations` | `LOLERExamination` |
| `management_review_inputs` | `ManagementReviewInput` |
| `management_reviews` | `ManagementReview` |
| `obsolete_document_records` | `ObsoleteDocumentRecord` |
| `onboarding_checklists` | `OnboardingChecklist` |
| `policies` | `Policy` |
| `policy_versions` | `PolicyVersion` |
| `risk_appetite_statements` | `RiskAppetiteStatement` |
| `risk_assessment_history` | `RiskAssessmentHistory` |
| `risk_assessments` | `RiskAssessment` |
| `risk_control_mappings` | `RiskControlMapping` |
| `risk_controls` | `OperationalRiskControl` |
| `risks` | `Risk` |
| `risks_v2` | `EnterpriseRisk` |
| `road_traffic_collisions` | `RoadTrafficCollision` |
| `roi_investments` | `ROIInvestment` |
| `rta_actions` | `RTAAction` |
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
