"""Recorded write-contract gaps present on ``main`` — the remediation roadmap.

Every entry here is a **real defect**, not an accepted exception. The guards in
``test_write_contract_guards.py`` use this file two ways:

* an ``xfail`` per entry, so ``pytest -rxX`` prints the outstanding list and a
  fixed entry surfaces as ``XPASS`` rather than sitting here forever;
* an active assertion that nothing appears which is *not* recorded here, so a
  newly added endpoint cannot quietly join the backlog.

That second use is the point of the file. The backlog is large enough that
failing on all of it would just mean the suite is permanently red and therefore
ignored; failing on *growth* is a gate that can actually stay green.

Regenerating: these lists are derived from ``app.openapi()``. When a gap is
fixed, delete its entry — the XPASS in CI tells you which one.

Counts at the time of writing (build 5b18b60; Guard 3 refreshed after #1385):
  * unknown-field rejection ....... 296 of 296 write schemas do not reject
  * response/request symmetry ..... 37 of 61 readable resources, 185 fields
  * write-only request fields ..... 16 operations, 31 fields
  * lookup/enum disagreement ...... 0 of 8 UI bindings (cleared: complaint_types
    / incident_types in #1385, ``severity_levels`` in B-9)
"""

from __future__ import annotations

# Guard 2 — write schemas that silently ignore unknown body fields.
#
# Pydantic defaults to ``extra="ignore"``, so a client that posts a field the
# model does not declare gets 201 and no indication the value was dropped.
# PX-168 is the visible symptom of this on ``ActionCreate``. ``ActionCreate`` /
# ``ActionUpdate`` already declare ``extra="forbid"``; they remain listed only
# until a dedicated backlog cleanup removes already-strict schemas. This PR
# converts ``AssetTypeCreate`` and ``AssetTypeUpdate`` (after ``AssessmentRunUpdate`` / ``AssessorGuidanceRequest``) and removes
# those two from the set so Guard 2 / round-trip start enforcing them.
KNOWN_LAX_WRITE_SCHEMAS: frozenset[str] = frozenset(
    {
        "BuilderBriefRequest",
        "BuilderQaRequest",
        "BulkApprovalRequest",
        "BulkReprocessRequest",
        "CampaignCreateRequestFE",
        "CampaignUpdateRequest",
        "CertificationStatusPatch",
        "ChecklistRequest",
        "ClauseCreate",
        "ClauseUpdate",
        "ComplaintCreate",
        "ComplaintUpdate",
        "ContractCreate",
        "ContractUpdate",
        "CostRecord",
        "CreateFromRecordRequest",
        "CustomerPackOmitApproveRequest",
        "CustomerPackOmitRequest",
        "DashboardCreate",
        "DashboardUpdate",
        "DecideStandardLinkRequest",
        "DeclineInput",
        "DeepRunCreate",
        "DefectActionCreate",
        "DefectCreate",
        "DefectUpdate",
        "DelegationRequest",
        "DiscussionMessageCreate",
        "DiscussionThreadCreate",
        "DisposalExecuteRequest",
        "DistributionCreate",
        "DocumentCreate",
        "DocumentUpdate",
        "DriverProfileCreate",
        "DriverProfileUpdate",
        "EmissionSourceCreate",
        "EngineerCreate",
        "EngineerLinkUserRequest",
        "EngineerUpdate",
        "EscalationLevelCreate",
        "EscalationLevelUpdate",
        "EscalationRequest",
        "EvidenceAssetUpdate",
        "EvidenceLinkRequest",
        "EvidencePatch",
        "ExternalAuditBulkReviewRequest",
        "ExternalAuditDraftReviewRequest",
        "ExternalAuditImportJobCreate",
        "FeatureFlagCreate",
        "FeatureFlagEvaluateRequest",
        "FeatureFlagUpdate",
        "FindingClassificationRequest",
        "FlagFindingRiskRequest",
        "FleetRecordCreate",
        "ForecastRequest",
        "FormFieldCreate",
        "FormFieldUpdate",
        "FormStepCreate",
        "FormStepUpdate",
        "FormTemplateCreate",
        "FormTemplateUpdate",
        "FromSignalRequest",
        "GapAnalysisRequest",
        "GenerateFromBriefRequest",
        "GenerateQuizRequest",
        "GroupCreateRequest",
        "GroupMembersRequest",
        "HsReportingPeriodInput",
        "ImprovementActionCreate",
        "IncidentCreate",
        "InductionResponseCreate",
        "InductionResponseUpdate",
        "InductionRunCreate",
        "InductionRunUpdate",
        "InterpretRequest",
        "InvestigationRunCreate",
        "InvestigationRunUpdate",
        "InvestigationTemplateCreate",
        "InvestigationTemplateUpdate",
        "KPICreate",
        "KRIUpdate",
        "KRIValueUpdate",
        "LibraryDocumentPatch",
        "LibraryRejectRequest",
        "LinkRequest",
        "LocationCreate",
        "LocationUpdate",
        "LogDocumentReadRequest",
        "LookupOptionCreate",
        "LookupOptionUpdate",
        "ManualTimelineEntryRequest",
        "MappingCreate",
        "MappingUpdate",
        "MatterLegalHoldCreate",
        "NearMissCreate",
        "NearMissUpdate",
        "NotificationPreferenceUpdate",
        "NotificationPreferencesUpdate",
        "OCRArtifactAckRequest",
        "OCRArtifactDisputeRequest",
        "OfferCampaignRequest",
        "OpenPackRequest",
        "PartnerApiTokenCreate",
        "PolicyCreate",
        "PolicyUpdate",
        "PromptTemplateRequest",
        "PushSubscriptionCreate",
        "QuestionGenerationRequest",
        "QuickReportCreate",
        "QuizSubmitRequest",
        "ROIInvestmentCreate",
        "RTAActionCreate",
        "RTAActionUpdate",
        "RTACreate",
        "RTAUpdate",
        "RecommendationRequest",
        "RefreshTokenRequest",
        "ReminderDefaultsUpdateRequest",
        "ReportRequest",
        "ReportingYearCreate",
        "ResearchRequest",
        "ResolveRequest",
        "ResolveWatchImpactRequest",
        "ResponseCreate",
        "RiskActionCreate",
        "RiskAssessmentCreate",
        "RiskAssessmentUpdate",
        "RiskControlCreate",
        "RiskControlUpdate",
        "RiskNoteCreate",
        "RiskOwnerUpdate",
        "RoleCreate",
        "RoleUpdate",
        "RunningSheetEntryCreate",
        "SIFAssessmentCreate",
        "SLAConfigurationCreate",
        "SLAConfigurationUpdate",
        "SafetyLookupMergeRequest",
        "SafetyLookupPreviewRequest",
        "SafetyLookupRejectRequest",
        "ScanKbRequest",
        "SecurityIncidentCreate",
        "SecurityRiskCreate",
        "SendNotificationRequest",
        "SignAssignmentRequest",
        "SignInput",
        "SignatureRequestCreate",
        "SimilarTemplatesRequest",
        "SnoozeAssignmentRequest",
        "StandardCreate",
        "StandardUpdate",
        "SuggestStandardLinksRequest",
        "SuggestionTriageResolve",
        "SupplierAssessmentCreate",
        "SystemSettingCreate",
        "SystemSettingUpdate",
        "TelemetryBatch",
        "TelemetryEvent",
        "TemplateCreate",
        "TenantBranding",
        "TenantCreate",
        "TenantInvite",
        "TenantUpdate",
        "TenantUserAdd",
        "TestUserRequest",
        "TextAnalysisRequest",
        "TrainingMatrixMatrixUpsertRequest",
        "TrainingMatrixNameMapUpsert",
        "TrainingMatrixNotifyRequest",
        "TrainingMatrixPersonRoleUpdate",
        "TrainingMatrixRequirementCreate",
        "TrainingMatrixRequirementSeedRequest",
        "TrainingMatrixRequirementUpdate",
        "TrainingTicketCreate",
        "TrainingTicketUpdate",
        "UpdateProfileRequest",
        "UserCreate",
        "UserUpdate",
        "UtilityReadingCreate",
        "VehicleRegistryUpdate",
        "VersionCreate",
        "WebEnrichRequest",
        "WebVitalsPayload",
        "WebhookSubscriptionCreate",
        "WebhookSubscriptionUpdate",
        "WidgetConfig",
        "WorkflowCreate",
        "WorkflowRuleCreate",
        "WorkflowRuleUpdate",
        "WorkflowStartRequest",
        "src__api__routes__audit_trail__ExportRequest",
        "src__api__routes__iso27001__AssetCreate",
        "src__api__routes__iso27001__AssetUpdate",
        "src__api__routes__iso27001__ControlUpdate",
        "src__api__routes__iso27001__IncidentUpdate",
        "src__api__routes__iso27001__RiskUpdate",
        "src__api__routes__risk_register__ControlCreate",
        "src__api__routes__risk_register__KRICreate",
        "src__api__routes__risk_register__RiskCreate",
        "src__api__routes__risk_register__RiskUpdate",
        "src__api__schemas__asset__AssetCreate",
        "src__api__schemas__asset__AssetUpdate",
        "src__api__schemas__incident__IncidentUpdate",
        "src__api__schemas__kri__KRICreate",
        "src__api__schemas__risk__RiskCreate",
        "src__api__schemas__risk__RiskUpdate",
        "src__api__schemas__standard__ControlCreate",
        "src__api__schemas__standard__ControlUpdate",
    }
)


# Guard 4 — state a resource returns that no create or update writer accepts.
#
# PX-168 in its general form: the API tells a client ``owner_id``, the client
# echoes it back, and there is no request field that can receive it. Keyed by
# response model because that is the stable identity of the resource.
KNOWN_ASYMMETRIC_RESPONSE_FIELDS: dict[str, tuple[str, ...]] = {
    "ActionOwnerNoteRead": ("action_key", "author_email", "author_id"),
    "ActionResponse": ("action_key", "audit_run_id", "clause_reference", "source_scheme", "source_title"),
    "AssessmentRunResponse": (
        "competency_gate_cleared",
        "competency_gate_mode",
        "competency_gate_reason",
        "debrief_notes",
        "debrief_signature",
        "latitude",
        "longitude",
        "outcome",
        "overall_notes",
        "responses",
        "supervisor_id",
        "template_version",
    ),
    "AssetResponse": ("external_id",),
    "AssetTypeResponse": ("approval_status", "source"),
    "AuditFindingResponse": ("clause_ids",),
    "AuditRunResponse": ("is_external_audit_import", "is_external_import_intake", "passed", "template_version"),
    "AuditTemplateResponse": ("external_id",),
    "CAPAResponse": ("verified_by_id",),
    "CampaignResponse": ("completed", "expired", "overdue", "pending", "status", "total_assigned"),
    "ComplaintResponse": (
        "compensation_offered",
        "department",
        "linked_risk_ids",
        "reporter_submission",
        "response_sla_state",
        "target_resolution_date",
    ),
    "DocumentReadLogResponse": ("user_id",),
    "DocumentResponse": (
        "ai_keywords",
        "ai_summary",
        "ai_tags",
        "category",
        "category_id",
        "department",
        "document_type",
        "duplicate_warning",
        "duplicate_warning_detail",
        "file_name",
        "file_size",
        "file_type",
        "indexing_error",
        "is_public",
        "is_statutory",
        "pel_doc_ref",
        "retention_until",
        "sensitivity",
        "site_location_id",
        "status",
    ),
    "EngineerResponse": ("external_id", "linked_user", "pams_technician_id"),
    "EvidenceAssetResponse": (
        "asset_type",
        "checksum_sha256",
        "content_type",
        "file_size_bytes",
        "original_filename",
        "source_id",
        "source_module",
        "storage_key",
        "thumbnail_storage_key",
    ),
    "ExternalAuditImportJobResponse": (
        "analysis_summary",
        "audit_scope",
        "audit_type",
        "auditor_name",
        "certificate_number",
        "classification_basis_json",
        "detected_scheme",
        "detected_scheme_confidence",
        "error_code",
        "error_detail",
        "evidence_preview_json",
        "extraction_method",
        "extraction_text_preview",
        "has_tabular_data",
        "improvement_summary_json",
        "issuer_name",
        "next_audit_date",
        "nonconformity_summary_json",
        "organization_name",
        "outcome_status",
        "positive_summary_json",
        "processing_warnings_json",
        "promote_attempt",
        "promote_failed",
        "promote_progress_json",
        "promote_succeeded",
        "promote_total",
        "promotion_summary_json",
        "provenance_json",
        "provider_model",
        "provider_name",
        "report_date",
        "scheme_version",
        "score_breakdown_json",
        "source_filename",
        "specialist_home_label",
        "specialist_home_path",
        "status",
    ),
    "IncidentResponse": (
        "immediate_actions",
        "investigator_id",
        "is_psif",
        "is_sif",
        "life_altering_potential",
        "linked_risk_ids",
        "reported_date",
        "reporter_submission",
        "witnesses",
    ),
    "InductionRunResponse": (
        "competency_gate_cleared",
        "competency_gate_mode",
        "competency_gate_reason",
        "responses",
        "supervisor_id",
        "template_version",
        "total_items",
    ),
    "InvestigationCommentResponse": ("author_id",),
    "InvestigationRunResponse": ("assigned_entity_reference",),
    "KRIResponse": ("current_status", "current_value", "last_updated", "trend_direction"),
    "LocationResponse": ("approval_status", "source"),
    "MappingResponse": ("mapped_clause_id", "primary_clause_id"),
    "MatterLegalHoldResponse": ("status",),
    "NearMissResponse": ("linked_risk_ids",),
    "PackResponse": (
        "closed_by_id",
        "findings",
        "internal_inputs",
        "opened_by_id",
        "status",
        "window_days",
        "window_end",
        "window_start",
    ),
    "PolicyAcknowledgmentResponse": (
        "due_date",
        "policy_id",
        "policy_version",
        "quiz_attempts",
        "quiz_passed",
        "reminders_sent",
        "requirement_id",
        "status",
        "time_spent_seconds",
        "user_id",
    ),
    # Compliance Schedule (Wave 0). ``outcome`` is decided by the completion
    # event itself (completed vs missed) rather than sent, and the three filing
    # fields are written by the Wave 2 library-filing bridge, not by a client.
    # ``external_id`` follows AssetResponse/AuditTemplateResponse: server-minted.
    "RecordResponse": ("external_id", "filing_error", "filing_status", "library_document_id", "outcome"),
    # ``status`` is derived from next_due_date per ADR-0020 (Current / Due soon /
    # Overdue / Missed), so it is computed on read and cannot be set.
    # ``fra_ocr_eligible`` is server-computed from template key / taxonomy +
    # active + site-scoped (matches FRA OCR draft create gate); clients must
    # not send it on create/update.
    "RequirementResponse": ("external_id", "status", "fra_ocr_eligible"),
    "RTAActionResponse": ("status",),
    "RTAResponse": ("reporter_submission",),
    "RiskActionItem": ("href", "source_id", "source_type", "status"),
    "SIFAssessmentResponse": ("sif_assessed_by_id", "sif_assessment_date"),
    "SignatureRequestResponse": ("status",),
    "TenantResponse": ("max_users",),
    "TrainingMatrixFrequencyChangeRequestResponse": (
        "proposed_by_email",
        "proposed_by_name",
        "proposed_by_user_id",
        "proposed_cells",
        "review_note",
        "reviewed_by_user_id",
        "status",
    ),
    "UserResponse": ("azure_oid", "last_login"),
    "VehicleRegistryResponse": (
        "compliance_status",
        "fire_extinguisher_expiry",
        "last_daily_check_pass",
        "pams_van_id",
        "road_tax_expiry",
        "tooling_calibration_expiry",
        "vehicle_reg",
    ),
    "src__api__schemas__standard__ClauseResponse": ("controls",),
}


# Guard 1 (static) — fields a client can send that the resource never returns.
#
# The write is accepted, but there is no read path to confirm it landed, which
# is the shape of PX-327. Keyed by ``METHOD /path`` so the owning endpoint is
# unambiguous.
KNOWN_UNREADABLE_REQUEST_FIELDS: dict[str, tuple[str, ...]] = {
    "POST /api/v1/actions/by-key/notes": ("key",),
    "PATCH /api/v1/audits/findings/{finding_id}": ("clause_ids_json_legacy",),
    "POST /api/v1/audits/runs": ("external_audit_type",),
    "POST /api/v1/audits/runs/{run_id}/findings": ("clause_ids_json_legacy",),
    "POST /api/v1/capa/{capa_id}/transition": ("comment",),
    # Compliance Schedule (Wave 0). Attaching evidence rebinds existing
    # EvidenceAsset rows onto the record by setting source_module /source_id on
    # the asset; the record itself stores no id list, so there is nothing on
    # RecordResponse to echo. A client confirms the attach by listing evidence
    # assets for the record, not by reading this response. Returning the ids
    # here would require a reverse join on every row of the record list.
    "POST /api/v1/compliance-schedule/records/{record_id}/evidence": ("evidence_asset_ids",),
    "POST /api/v1/compliance-schedule/requirements/{requirement_id}/records": ("evidence_asset_ids",),
    "POST /api/v1/document-campaigns/campaigns": (
        "audience",
        "audience_department",
        "audience_engineer_ids",
        "audience_group_id",
        "audience_role",
        "audience_user_ids",
    ),
    "POST /api/v1/investigations/from-record": ("source_id", "source_type"),
    "PATCH /api/v1/investigations/{investigation_id}": ("closure_override", "closure_override_reason"),
    "POST /api/v1/investigations/{investigation_id}/comments": ("body",),
    "POST /api/v1/policy-acknowledgments/{acknowledgment_id}/acknowledge": ("acceptance_statement", "signature_data"),
    "POST /api/v1/signatures/requests": (
        "document_id",
        "expires_in_days",
        "metadata",
        "reminder_frequency",
        "require_all",
    ),
    "POST /api/v1/tenants/": ("admin_email",),
    "PUT /api/v1/tenants/{tenant_id}/branding": ("accent_color", "custom_css", "favicon_url", "secondary_color"),
    "POST /api/v1/training-matrix/requirements/matrix/propose": ("cells",),
    "POST /api/v1/users/": ("auth_provider",),
}


# Guard 3 — seeded lookup options the paired API field rejects with 422.
#
# Keyed by (lookup category, request model, field). The values are the option
# codes a freshly seeded tenant offers in its form that the backend enum does
# not contain, so choosing them is an unavoidable 422.
#
# This backlog is empty, and there is machinery to keep it that way. All three
# categories a UI binding points at — ``complaint_types`` / ``incident_types``
# (repaired in #1385, PX-281/282, R22-01) and ``severity_levels`` (B-9, the
# shared five-value severity set) — are registered in ``lookup_enum_contract``
# and held by the seed test, the admin write guard and the integration probe.
# ``test_enum_backed_categories_have_no_recorded_gaps`` fails if one is recorded
# here again, so a regression has to be fixed rather than re-xfailed.
KNOWN_LOOKUP_ENUM_GAPS: dict[tuple[str, str, str], tuple[str, ...]] = {}
