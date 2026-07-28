"""Public privacy disclosure endpoints (Path-to-10 S15).

Provides machine-readable privacy contact details, data-lifecycle
capability flags, sub-processor disclosure, DPIA status, and a stub
Article 30-style data-processing register — without authentication.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from src.core.ai_provider_disclosure import (
    HOSTS_PLATFORM_DATA,
    RETAINS_CONTENT,
    TRANSIENT_PROCESSING,
    UNKNOWN,
    credentialed_provider_names,
    provider_by_register_name,
)
from src.core.retention_config import DEFAULT_RETENTION_POLICIES

router = APIRouter(prefix="/privacy", tags=["Privacy"])

_DEFAULT_SECURITY_EMAIL = "security@plantexpand.com"
_DEFAULT_PRIVACY_EMAIL = "privacy@plantexpand.com"

# Machine-readable DPIA close-out status (docs/compliance/dpia-quality-governance-platform.md).
# Flipped to signed after operator-confirmed DPO §9 / EA-03 close-out (2026-07-12).
_DPIA_STATUS = "signed"
_DPIA_DOC = "docs/compliance/dpia-quality-governance-platform.md"
_DPIA_EVIDENCE = "docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md"


def _security_email() -> str:
    return (os.getenv("SECURITY_CONTACT_EMAIL") or _DEFAULT_SECURITY_EMAIL).strip()


def _privacy_email() -> str:
    return (os.getenv("PRIVACY_CONTACT_EMAIL") or _DEFAULT_PRIVACY_EMAIL).strip()


def _as_of() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _retention_disclosure() -> dict[str, Any]:
    """Machine-readable retention SSOT summary (docs/privacy/data-retention-policy.md §7b)."""
    soft_delete_first = all(policy.soft_delete_first for policy in DEFAULT_RETENTION_POLICIES.values())
    return {
        "policy_doc": "docs/privacy/data-retention-policy.md",
        "config_module": "src.core.retention_config",
        "soft_delete_first": soft_delete_first,
        "matter_level_legal_hold_schema": True,
        "matter_level_legal_hold_ssot": "matter_legal_holds",
        "matter_level_legal_hold_api": "/api/v1/legal-holds",
        "matter_level_legal_hold_enforcement": "not_yet_wired_to_retention_workers",
        "purge_schedule": "daily 02:00 UTC (Celery Beat run-data-retention)",
        "entity_horizons_days": {
            entity: policy.retention_days for entity, policy in DEFAULT_RETENTION_POLICIES.items()
        },
        "note": (
            "Horizons mirror DEFAULT_RETENTION_POLICIES; soft-delete-first is coded. "
            "Matter-level holds have a tenant-scoped persistence SSOT and admin API. "
            "Retention workers do not yet consume active matter holds, so this is not a "
            "claim of automated purge prevention — see retention policy §7a."
        ),
    }


def _dpia_disclosure() -> dict[str, Any]:
    """DPIA artifact pointers plus live close-out status field."""
    return {
        "status": _DPIA_STATUS,
        "status_doc": _DPIA_DOC,
        "evidence": _DPIA_EVIDENCE,
        "platform": _DPIA_DOC,
        "ocr_ai_import": "docs/compliance/dpia-ocr-ai-import.md",
        "incidents": "docs/privacy/dpia-incidents.md",
        "checklist": "docs/privacy/dpia-checklist.md",
        "attestation_pack": "docs/compliance/s15-dpia-art30-attestation-pack.md",
        "article_30_checklist": "docs/compliance/article-30-ropa-checklist.md",
        "governance_link": "docs/governance/privacy-ocr-ai-dpia.md",
        "note": (
            "status=signed after EA-03 DPO §9 close-out attested 2026-07-12 "
            "(evidence: docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md). "
            "EA-01/EA-02/EA-04 remain open — not claimed closed here."
        ),
    }


def _technical_organisational_measures() -> dict[str, Any]:
    """Art. 30(1)(g) general TOM / security-measures disclosure (unsigned stub).

    Points at documentary sources only — does **not** claim EA-02 pen-test
    close-out or invent DPO acceptance of residual risk.
    """
    return {
        "summary_doc": "docs/security/security-baseline.md",
        "dpia_section": "docs/compliance/dpia-quality-governance-platform.md",
        "dpia_section_ref": "§5 Technical and organisational measures",
        "controls": [
            "encryption_at_rest_and_in_transit",
            "rbac_and_tenant_isolation",
            "soft_delete_and_retention_jobs",
            "key_vault_secrets",
            "structured_audit_logging",
            "ai_providers_fail_soft_when_credentials_absent",
        ],
        "note": (
            "General Art. 30(1)(g) description for auditor readability only. "
            "Not a substitute for EA-02 external penetration testing; "
            "DPO §9 / EA-03 remain unsigned. AI providers are off in code defaults "
            "but are credentialed and active in production — see subprocessors."
        ),
    }


def _optional_ai_transfer_status() -> str:
    """Honest AI transfer posture based on which provider credentials are present.

    Derived from the disclosure SSOT rather than the OCR-only readiness view, so
    embedding and vector-database credentials count too.
    """
    if credentialed_provider_names():
        return "keys_present_pending_vendor_dpa_confirmation"
    return "pending_vendor_dpa_before_production_keys"


def _international_transfers() -> dict[str, Any]:
    """Art. 30(1)(e) international transfers / safeguards summary (unsigned stub).

    Mirrors GDPR §7 + subprocessor ``transfer_mechanism`` fields. Does **not**
    invent signed vendor DPAs or claim production AI transfers are approved.
    """
    subprocessors = _subprocessors()
    return {
        "primary_hosting_region": "UK South",
        "primary_hosting_mechanism": "uk_eea_hosting",
        "policy_doc": "docs/compliance/gdpr-compliance.md",
        "policy_section_ref": "§7 International Transfers",
        "dpia_refs": [
            "docs/compliance/dpia-quality-governance-platform.md",
            "docs/compliance/dpia-ocr-ai-import.md",
        ],
        "default_posture": (
            "Primary platform processing is hosted in Azure UK South (UK/EEA). "
            "AI subprocessors are enabled in production; their hosting regions and "
            "transfer safeguards are not established in this repository and must be "
            "treated as third-country transfers until the controller confirms them."
        ),
        "optional_ai_transfer_status": _optional_ai_transfer_status(),
        "subprocessor_transfer_mechanisms": [
            {
                "name": sp["name"],
                "transfer_mechanism": sp["transfer_mechanism"],
                "optional": sp["optional"],
                "retains_content": sp["retains_content"],
                "activation_status": sp["activation"]["status"],
            }
            for sp in subprocessors
        ],
        "retaining_subprocessors": [sp["name"] for sp in subprocessors if sp["retains_content"] and sp["optional"]],
        "unknown_transfer_mechanisms": [sp["name"] for sp in subprocessors if sp["transfer_mechanism"] == UNKNOWN],
        "note": (
            "Art. 30(1)(e) readability only — unsigned stub. Does not invent "
            "signed vendor DPAs; does not flip dpia.status. Transfer mechanisms "
            "listed as unknown are genuinely unestablished in the repository — a "
            "lawful-sounding placeholder would make this register false. "
            "retaining_subprocessors names AI processors that hold content rather "
            "than returning a result and keeping nothing."
        ),
    }


def _roles_and_contacts() -> dict[str, Any]:
    """Art. 30 roles + contact pointers (unsigned stub).

    Surfaces controller / processor / DPO / privacy / security contact shape for
    auditor readability. Does **not** invent a named DPO or claim DPO appointment.
    Tenant controllers supply their own legal-entity contact in their ROPA.
    """
    privacy = _privacy_email()
    security = _security_email()
    return {
        "schema": "article-30-roles-and-contacts/v1",
        "controller": {
            "role": "controller",
            "identity": "tenant_organisation",
            "contact_source": "per_tenant_dpa_schedule",
            "note": (
                "Controller legal name + contact live in each tenant's DPA / ROPA — "
                "not hardcoded in this platform stub."
            ),
        },
        "processor": {
            "role": "processor_platform_operator",
            "identity": "Plantexpand (QGP platform operator)",
            "privacy_contact": privacy,
            "security_contact": security,
            "security_txt": "/.well-known/security.txt",
        },
        "dpo": {
            "status": "appointed_by_controller_or_operator_when_required",
            "contact_email": None,
            "note": (
                "DPO name/email are not invented in-repo. When appointed, publish via "
                "env/policy and confirm in the controller/operator ROPA — "
                "do not forge DPO identity here."
            ),
        },
        "privacy_contact": privacy,
        "security_contact": security,
        "live_endpoints": {
            "contact": "/api/v1/privacy/contact",
            "register": "/api/v1/privacy/data-processing-register",
        },
        "note": (
            "Unsigned Art. 30 roles/contacts summary for auditor readability. "
            "Does not invent DPO identity, signed DPIA, or full controller ROPA."
        ),
    }


_OCR_AI_DPIA_DOC = "docs/compliance/dpia-ocr-ai-import.md"

# Written confirmation from the data controller / accountable owner that these
# processors are switched on and in use in production. Recorded so the register
# does not present live processing as a hypothetical.
_CONTROLLER_CONFIRMATION = "controller_written_confirmation_2026-07-28"
_CONTROLLER_CONFIRMED_ACTIVE = frozenset(
    {
        "Mistral AI",
        "Google Gemini",
        "Anthropic",
        "OpenAI",
        "Voyage AI",
        "Pinecone",
    }
)

# Third-country posture shared by every AI processor below: the repository
# configures no region pin and holds no vendor DPA / SCC / IDTA artifact, so
# neither the hosting region nor the transfer safeguard can be stated here.
_NO_REGION_CONTROL_NOTE = (
    "Hosting region is not established in this repository — no residency option is "
    "configured on this provider's client. Treat as a third-country transfer until "
    "the controller confirms the vendor's processing location in writing."
)
_NO_SAFEGUARD_ARTIFACT = "no_vendor_dpa_scc_or_idta_artifact_in_repository"


def _ai_subprocessor_entries() -> list[dict[str, Any]]:
    """Register rows for third-party AI processors reachable from code.

    Descriptive fields are derived from reading the call paths, not from vendor
    marketing: ``data_transmitted`` states what the provider actually receives
    and ``retention_posture`` distinguishes providers that hold content from
    providers that return a result and keep nothing on this platform's behalf.
    """
    return [
        {
            "name": "Azure AI Document Intelligence",
            "role": "ai_ocr_processor",
            "purposes": ["ocr", "dual_ocr_consensus", "library_ocr_failover"],
            "regions": ["UK South"],
            "region_evidence": (
                "docs/compliance/e4-dual-ocr-redaction-gate.md — dedicated resource qgp-docintel "
                "provisioned in uksouth. The runtime endpoint comes from configuration, so this "
                "register cannot verify the deployed value matches that resource."
            ),
            "transfer_mechanism": "uk_eea_hosting_per_e4_gate_resource_evidence",
            "transfer_safeguard_status": "microsoft_dpa_operator_confirms_resource_matches_e4_evidence",
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": (
                "Sends document bytes for OCR and consumes the returned text. This platform "
                "stores no content with the provider; vendor-side retention is governed by the "
                "Azure resource configuration, which is not visible in this repository."
            ),
            "data_transmitted": [
                "library_document_bytes_when_native_and_mistral_ocr_are_thin_or_failed",
                "external_audit_document_bytes_on_dual_ocr_paths",
            ],
            "enabled_when": (
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT + AZURE_DOCUMENT_INTELLIGENCE_KEY set "
                "AND AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD true"
            ),
            "authorised_by": "docs/compliance/e4-dual-ocr-redaction-gate.md",
            "unknown_fields": ["deployed_endpoint_region_verification"],
            "note": (
                "Enabled in production (azure_di.enabled_in_prod=true) and authorised by the "
                "closed E4 dual-OCR gate, which records a dedicated qgp-docintel resource in "
                "uksouth. Must never use the Jobsheet Document Intelligence resource. This is "
                "the only AI processor here with a documented UK region — it is claimed on that "
                "documentary evidence, not on an assumption about the vendor."
            ),
        },
        {
            "name": "Mistral AI",
            "role": "ai_ocr_processor",
            "purposes": ["ocr", "structured_extraction"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": (
                "Receives document content and returns OCR text / structured findings. "
                "OCR requests set include_image_base64=false. Vendor-side retention terms "
                "are a contractual question this repository does not answer."
            ),
            "data_transmitted": [
                "external_audit_document_bytes_and_page_images",
                "library_document_bytes_when_native_extraction_is_thin_or_empty",
                "extracted_document_text_for_structured_analysis",
            ],
            "enabled_when": "MISTRAL_API_KEY configured",
            "unknown_fields": ["regions", "transfer_mechanism"],
            "note": _NO_REGION_CONTROL_NOTE,
        },
        {
            "name": "Google Gemini",
            "role": "ai_review_processor",
            "purposes": ["multimodal_review"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": (
                "Receives document content for a second-pass visual review and returns review "
                "output. No content is stored with the provider by this platform."
            ),
            "data_transmitted": ["external_audit_document_bytes_for_multimodal_review"],
            "enabled_when": "GOOGLE_GEMINI_API_KEY configured",
            "unknown_fields": ["regions", "transfer_mechanism"],
            "note": _NO_REGION_CONTROL_NOTE,
        },
        {
            "name": "Anthropic",
            "role": "ai_analysis_processor",
            "purposes": [
                "library_document_metadata_analysis",
                "governed_knowledge_evidence_mapping",
                "training_quiz_generation",
                "iso_compliance_analysis",
                "incident_corrective_action_recommendations",
                "health_and_safety_analyst_synthesis",
                "audit_builder_and_challenge_generation",
            ],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": (
                "Prompt content is transmitted and the completion is returned; this platform "
                "stores nothing with the provider. Vendor-side prompt retention and any "
                "training exclusion are contractual, not established in this repository."
            ),
            "data_transmitted": [
                "library_document_text_up_to_50000_characters_per_analysis",
                "incident_descriptions_for_corrective_action_recommendations",
                "aggregated_incident_and_near_miss_themes_with_case_reference_numbers",
                "audit_finding_and_clause_text",
            ],
            "enabled_when": "ANTHROPIC_API_KEY configured",
            "unknown_fields": ["regions", "transfer_mechanism"],
            "note": (
                "Widest AI data reach of any processor here: it is the preferred client for "
                "library document analysis *and* for case-register assistance (incidents, "
                "near misses, audits), so free-text personal and possibly special-category "
                "narratives can be transmitted. " + _NO_REGION_CONTROL_NOTE
            ),
        },
        {
            "name": "OpenAI",
            "role": "ai_analysis_processor",
            "purposes": ["fallback_llm_analysis_for_shared_ai_client_paths"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": (
                "Prompt content is transmitted and the completion is returned; this platform "
                "stores nothing with the provider."
            ),
            "data_transmitted": [
                "same_prompt_content_as_anthropic_on_shared_ai_client_paths",
                "library_document_text_incident_and_audit_text_when_selected",
            ],
            "enabled_when": "OPENAI_API_KEY configured (selected via AI_PROVIDER or Anthropic fallback)",
            "unknown_fields": ["regions", "transfer_mechanism"],
            "note": (
                "Reached through the shared AI client (src/domain/services/ai_models.py). Which "
                "of Anthropic / OpenAI serves a given request depends on AI_PROVIDER and key "
                "presence at runtime, so both must be disclosed. " + _NO_REGION_CONTROL_NOTE
            ),
        },
        {
            "name": "Voyage AI",
            "role": "ai_embedding_processor",
            "purposes": ["document_chunk_embeddings", "search_query_embeddings"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": (
                "Receives chunk text and returns vectors. Nothing is stored with the provider "
                "by this platform — but note the vectors it returns are then persisted in "
                "Pinecone, which is a separate, retaining transfer."
            ),
            "data_transmitted": [
                "full_text_of_every_library_document_chunk_at_index_time",
                "user_supplied_semantic_search_query_text",
            ],
            "enabled_when": "VOYAGE_API_KEY configured",
            "unknown_fields": ["regions", "transfer_mechanism"],
            "note": _NO_REGION_CONTROL_NOTE,
        },
        {
            "name": "Pinecone",
            "role": "vector_database_processor",
            "purposes": ["library_semantic_index_storage", "semantic_search_and_governed_kb_retrieval"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": RETAINS_CONTENT,
            "retained_data": [
                "embedding_vectors_derived_from_library_document_chunks",
                "chunk_content_preview_first_200_characters_verbatim",
                "document_id",
                "tenant_id",
                "chunk_index",
                "chunk_heading",
                "page_number",
                "document_type",
            ],
            "retention_note": (
                "This is a persistent transfer, not transient processing. Vectors and their "
                "metadata stay in the vendor-hosted index until this platform deletes them by "
                "vector ID (reindex supersession or library disposal). There is no independent "
                "retention horizon on the index: it follows the source document's lifecycle, "
                "and a failed delete leaves content in the index — the failure is logged as an "
                "error but not retried automatically."
            ),
            "data_transmitted": [
                "embedding_vectors_for_each_library_document_chunk",
                "chunk_content_preview_first_200_characters_verbatim",
                "chunk_and_document_identifiers_plus_tenant_id",
                "query_vector_and_tenant_filter_at_search_time",
            ],
            "index_scope": "library_documents_table_only_not_case_register_records",
            "index_name_config": "PINECONE_INDEX (default qgp-documents)",
            "deletion_paths": [
                "src/domain/services/index_job_service.py::delete_pending_stale_vectors",
                "src/domain/services/document_library_disposal_service.py",
            ],
            "enabled_when": "PINECONE_API_KEY configured (with VOYAGE_API_KEY to produce vectors)",
            "unknown_fields": ["regions", "transfer_mechanism"],
            "note": (
                "Highest-severity transfer in this register: document-derived content is "
                "transmitted to and RETAINED BY a vendor-hosted vector database. Content "
                "reaching the index comes only from the governance document library "
                "(documents table); incident, near-miss and RTA records are not indexed, "
                "though a document uploaded to the library may itself contain case content. "
                "The configured serverless environment identifier does not resolve to a "
                "country in this repository. " + _NO_REGION_CONTROL_NOTE
            ),
        },
        {
            "name": "Genspark.ai",
            "role": "ai_analysis_processor",
            "purposes": ["legacy_fallback_llm_analysis"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": "Prompt content transmitted, completion returned; nothing stored by this platform.",
            "data_transmitted": ["prompt_content_on_shared_ai_client_paths_when_selected"],
            "enabled_when": "GENSPARK_API_KEY configured and no preferred direct provider available",
            "unknown_fields": ["regions", "transfer_mechanism", "production_activation"],
            "note": (
                "Legacy shared-AI-client fallback still present in code. Disclosed because the "
                "code path exists; the controller has not confirmed it as active, so its "
                "activation status is reported as unconfirmed rather than asserted either way."
            ),
        },
        {
            "name": "Perplexity",
            "role": "ai_research_processor",
            "purposes": ["governance_horizon_scanning", "audit_builder_research"],
            "regions": [UNKNOWN],
            "transfer_mechanism": UNKNOWN,
            "transfer_safeguard_status": _NO_SAFEGUARD_ARTIFACT,
            "retention_posture": TRANSIENT_PROCESSING,
            "retained_data": [],
            "retention_note": "Research query transmitted, findings returned; nothing stored by this platform.",
            "data_transmitted": [
                "horizon_scan_query_text_derived_from_document_titles_and_topics",
                "audit_builder_research_query_text",
            ],
            "enabled_when": "PERPLEXITY_API_KEY configured (horizon provider or audit-builder research)",
            "unknown_fields": ["regions", "transfer_mechanism", "production_activation"],
            "note": (
                "Disclosed because the live code path exists; the controller has not confirmed "
                "it as active. Note the audit-builder research helper uses the key even when "
                "library_horizon_provider is left at stub."
            ),
        },
    ]


def _subprocessors() -> list[dict[str, Any]]:
    """Public sub-processor list (Art. 28 / Art. 30(1)(d) disclosure).

    Infrastructure plus every third-party AI processor reachable from code.
    ``activation.status`` states the production position (controller confirmation
    or a closed gate), while
    ``activation.credentials_present_in_this_environment`` reports what the
    deployment serving this response can actually reach — read from the same
    configuration the services read (``src.core.ai_provider_disclosure``),
    presence only, never a secret value. A processor that is reachable but absent
    here is a disclosure gap, which
    ``tests/unit/test_ai_provider_disclosure.py`` fails on.
    """
    credentialed = credentialed_provider_names()

    subprocessors: list[dict[str, Any]] = [
        {
            "name": "Microsoft Azure",
            "role": "infrastructure_processor",
            "purposes": [
                "app_hosting",
                "postgresql",
                "blob_storage",
                "entra_id",
                "log_analytics",
                "key_vault",
            ],
            "regions": ["UK South"],
            "region_evidence": "docs/compliance/gdpr-compliance.md §7; docs/compliance/dpia-quality-governance-platform.md",
            "transfer_mechanism": "uk_eea_hosting",
            "transfer_safeguard_status": "operator_confirms_microsoft_dpa",
            "retention_posture": HOSTS_PLATFORM_DATA,
            "retains_content": True,
            "retained_data": [
                "all_platform_records_and_uploaded_files",
                "operational_and_audit_logs",
            ],
            "retention_note": "Primary hosting; retention follows src.core.retention_config horizons.",
            "data_transmitted": ["all_platform_data_in_scope_of_hosting"],
            "optional": False,
            "activation": {
                "status": "active_in_production",
                "controller_confirmed": True,
                "credentials_present_in_this_environment": None,
                "evidence": "primary hosting — not credential-gated in this register",
            },
            "unknown_fields": [],
            "dpa_doc": "docs/compliance/gdpr-compliance.md",
        }
    ]

    for entry in _ai_subprocessor_entries():
        name = entry["name"]
        provider = provider_by_register_name(name)
        controller_confirmed = name in _CONTROLLER_CONFIRMED_ACTIVE
        if name == "Azure AI Document Intelligence":
            status = "active_in_production_e4_gate_closed"
            evidence = "azure_di.enabled_in_prod=true; docs/compliance/e4-dual-ocr-redaction-gate.md"
            controller_confirmed = True
        elif controller_confirmed:
            status = "active_in_production_controller_confirmed"
            evidence = _CONTROLLER_CONFIRMATION
        else:
            status = "code_path_present_activation_not_confirmed"
            evidence = "no controller confirmation on file in this repository"
        subprocessors.append(
            {
                **entry,
                "optional": True,
                "retains_content": entry["retention_posture"] == RETAINS_CONTENT,
                "activation": {
                    "status": status,
                    "controller_confirmed": controller_confirmed,
                    # Status describes production; this flag describes the deployment
                    # serving the response, which may be a lower environment.
                    "credentials_present_in_this_environment": name in credentialed,
                    "evidence": evidence,
                },
                "credential_settings_fields": sorted(provider.config_fields) if provider else [],
                "code_paths": list(provider.code_paths) if provider else [],
                "dpa_doc": entry.get("dpa_doc", _OCR_AI_DPIA_DOC),
            }
        )

    return subprocessors


def _processing_activities() -> list[dict[str, Any]]:
    """Stub Article 30 register rows (high-level; not a full ROPA).

    Additive ``purpose`` / ``data_subject_categories`` fields close Art. 30
    checklist gaps C/D for auditor readability — still ``article_30_stub``.
    """
    activities: list[dict[str, Any]] = [
        {
            "activity_id": "user-accounts",
            "name": "User account administration",
            "purpose": "Authenticate and authorise platform users; manage roles and tenant membership",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "contractors", "platform_administrators"],
            "data_categories": ["email", "name", "role"],
            "retention_days": DEFAULT_RETENTION_POLICIES["users_deleted"].retention_days,
            "retention_note": "Account lifetime + users_deleted horizon post-deactivation",
            "storage": "postgresql",
        },
        {
            "activity_id": "incidents",
            "name": "Incident / H&S reporting",
            "purpose": "Record, investigate, and report workplace health and safety incidents",
            "lawful_basis": "legal_obligation",
            "data_subject_categories": ["employees", "contractors", "visitors", "injured_persons"],
            "data_categories": ["description", "location", "personnel", "injury_details"],
            "retention_days": DEFAULT_RETENTION_POLICIES["incidents"].retention_days,
            "storage": "postgresql",
        },
        {
            "activity_id": "audit-findings",
            "name": "Audit findings and evidence",
            "purpose": "Capture audit findings, evidence references, and related quality records",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "auditors", "auditees"],
            "data_categories": ["finding_text", "evidence_references"],
            "retention_days": DEFAULT_RETENTION_POLICIES["audit_runs"].retention_days,
            "storage": "postgresql_and_azure_blob",
        },
        {
            "activity_id": "ocr-ai-import",
            "name": "External audit OCR / AI import",
            "purpose": "Extract structured findings from external audit documents via optional OCR/AI",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "auditees", "document_authors"],
            "data_categories": ["document_content", "extracted_findings"],
            "retention_days": None,
            "retention_note": "Per parent import job + evidence retention policy",
            "storage": "azure_blob_plus_optional_ai_processors",
            "subprocessors": ["Mistral AI", "Google Gemini", "Azure AI Document Intelligence"],
            "third_country_retention": False,
            "dpia": "docs/compliance/dpia-ocr-ai-import.md",
        },
        {
            "activity_id": "library-document-index",
            "name": "Governance library document indexing and semantic search",
            "purpose": (
                "OCR, chunk, analyse and embed uploaded governance library documents so they "
                "are semantically searchable and can be mapped to compliance evidence"
            ),
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "contractors", "document_authors", "named_third_parties"],
            "data_categories": [
                "document_content",
                "document_chunk_text",
                "chunk_content_previews",
                "embedding_vectors",
                "ai_derived_summaries_tags_and_entities",
            ],
            "retention_days": None,
            "retention_note": (
                "Chunks and vectors follow the source document lifecycle. Vectors in the "
                "third-party index are removed on reindex supersession or library disposal; "
                "there is no independent horizon and no automatic retry if a delete fails."
            ),
            "storage": "postgresql_azure_blob_and_third_party_vector_index",
            "subprocessors": [
                "Mistral AI",
                "Azure AI Document Intelligence",
                "Anthropic",
                "OpenAI",
                "Voyage AI",
                "Pinecone",
            ],
            "third_country_retention": True,
            "third_country_retention_note": (
                "Pinecone retains embedding vectors plus verbatim 200-character chunk previews "
                "and tenant/document identifiers until this platform deletes them."
            ),
            "dpia": "docs/compliance/dpia-ocr-ai-import.md",
        },
        {
            "activity_id": "ai-assisted-case-analysis",
            "name": "AI-assisted analysis of case-register and audit records",
            "purpose": (
                "Optional AI assistance over incident, near-miss and audit records — corrective "
                "action recommendations, health and safety analyst notes, audit generation and "
                "challenge, and ISO compliance analysis"
            ),
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "contractors", "injured_persons", "auditees"],
            "data_categories": [
                "incident_descriptions",
                "near_miss_and_incident_theme_summaries",
                "case_reference_numbers",
                "audit_finding_text",
            ],
            "retention_days": DEFAULT_RETENTION_POLICIES["incidents"].retention_days,
            "retention_note": (
                "Source records follow their own horizons; prompts are transmitted to the AI "
                "processor and not persisted with the processor by this platform."
            ),
            "storage": "postgresql_plus_transient_ai_processor_transmission",
            "subprocessors": ["Anthropic", "OpenAI", "Genspark.ai"],
            "third_country_retention": False,
            "third_country_retention_note": (
                "No content is stored with these processors by this platform, but free-text "
                "injury and incident narratives may leave the UK/EEA in the prompt."
            ),
            "dpia": "docs/compliance/dpia-ocr-ai-import.md",
        },
        {
            "activity_id": "auth-and-request-logs",
            "name": "Authentication and API request logs",
            "purpose": "Security monitoring, abuse detection, and operational troubleshooting",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["authenticated_users", "api_clients"],
            "data_categories": ["login_times", "ip_addresses", "tenant_id", "user_id"],
            "retention_days": DEFAULT_RETENTION_POLICIES["session_logs"].retention_days,
            "storage": "structured_logs_and_log_analytics",
        },
        {
            "activity_id": "complaints",
            "name": "Complaints / grievance handling",
            "purpose": "Receive, investigate, and resolve complaints and grievances",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["complainants", "employees", "third_parties"],
            "data_categories": ["complaint_text", "complainant_contact", "outcome"],
            "retention_days": DEFAULT_RETENTION_POLICIES["complaints"].retention_days,
            "storage": "postgresql",
        },
        {
            "activity_id": "near-misses",
            "name": "Near-miss / hazard reporting",
            "purpose": "Record near-miss and hazard reports to prevent future incidents",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "contractors", "reporters"],
            "data_categories": ["description", "location", "reporter"],
            "retention_days": DEFAULT_RETENTION_POLICIES["near_misses"].retention_days,
            "storage": "postgresql",
        },
        {
            "activity_id": "capa",
            "name": "Corrective and preventive actions (CAPA)",
            "purpose": "Track corrective and preventive actions arising from audits and incidents",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "action_owners"],
            "data_categories": ["action_text", "owner", "linked_finding_refs"],
            "retention_days": DEFAULT_RETENTION_POLICIES["audit_runs"].retention_days,
            "retention_note": "Aligned to audit_runs horizon pending discrete CAPA retention key",
            "storage": "postgresql",
        },
        {
            "activity_id": "risk-register",
            "name": "Enterprise / operational risk register",
            "purpose": "Maintain operational and enterprise risk records and control owners",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["employees", "risk_owners"],
            "data_categories": ["risk_description", "owner", "controls"],
            "retention_days": DEFAULT_RETENTION_POLICIES["audit_runs"].retention_days,
            "retention_note": "Aligned to audit_runs horizon pending discrete risk retention key",
            "storage": "postgresql",
        },
        {
            "activity_id": "rta",
            "name": "Road traffic accident (RTA) records",
            "purpose": "Record and investigate road traffic accidents involving the organisation",
            "lawful_basis": "legitimate_interest",
            "data_subject_categories": ["drivers", "passengers", "third_parties", "injured_persons"],
            "data_categories": ["incident_details", "vehicle", "parties"],
            "retention_days": DEFAULT_RETENTION_POLICIES["incidents"].retention_days,
            "retention_note": "Aligned to incidents horizon; may include special-category / injury data",
            "storage": "postgresql",
        },
    ]
    return [
        {
            **activity,
            "record_status": "platform_scope_documented_pending_controller_review",
            "controller_ropa_action": "confirm_or_complete_in_controller_record",
            "source_documents": [
                "docs/compliance/gdpr-compliance.md",
                "docs/compliance/article-30-ropa-checklist.md",
            ],
        }
        for activity in activities
    ]


@router.get("/contact")
async def privacy_contact() -> dict[str, Any]:
    """Public privacy / security contact and lifecycle capability flags.

    Surfaces RFC 9116 security.txt pointers plus documented soft-delete /
    legal-hold support on evidence assets (C4-adjacent attachments), a
    retention SSOT summary under ``retention``, sub-processors, and DPIA status.
    """
    security = _security_email()
    privacy = _privacy_email()
    return {
        "privacy_contact": privacy,
        "security_contact": security,
        "security_txt": "/.well-known/security.txt",
        "gdpr_routes": {
            "export": "/api/v1/gdpr/me/data-export",
            "erasure": "/api/v1/gdpr/me/data-erasure",
            "erasure_status": "/api/v1/gdpr/me/data-erasure/status",
        },
        "data_processing_register": "/api/v1/privacy/data-processing-register",
        "dpia": _dpia_disclosure(),
        "subprocessors": _subprocessors(),
        "data_lifecycle": {
            "soft_delete": True,
            "soft_delete_mixin": "src.domain.models.base.SoftDeleteMixin",
            "evidence_legal_hold": True,
            "evidence_legal_hold_enum": "EvidenceRetentionPolicy.LEGAL_HOLD",
            "evidence_entity": "evidence_assets",
            "note": (
                "Evidence assets support soft delete (deleted_at) and legal hold "
                "via retention_policy=legal_hold; purge jobs must skip held assets."
            ),
        },
        "retention": _retention_disclosure(),
        "as_of": _as_of(),
    }


@router.get("/data-processing-register")
async def data_processing_register() -> dict[str, Any]:
    """Stub Article 30-style data-processing register (ROPA summary).

    High-level, machine-readable inventory for Path-to-10 S15 compliance LIVE.
    Not a substitute for the full controller ROPA / DPO records.
    """
    return {
        "register_kind": "article_30_stub",
        "status": "stub",
        "completion_status": "structured_platform_scope_pending_privacy_lead_and_controller_review",
        "register_schema": "article-30-platform-register/v3",
        "controller": "tenant_organisation",
        "processor_operator": "Plantexpand (QGP platform operator)",
        "policy_doc": "docs/compliance/gdpr-compliance.md",
        "dpia": {
            "status": _DPIA_STATUS,
            "status_doc": _DPIA_DOC,
            "attestation_pack": "docs/compliance/s15-dpia-art30-attestation-pack.md",
        },
        "ropa_checklist": "docs/compliance/article-30-ropa-checklist.md",
        "roles_and_contacts": _roles_and_contacts(),
        "technical_organisational_measures": _technical_organisational_measures(),
        "international_transfers": _international_transfers(),
        "subprocessors": _subprocessors(),
        "activities": _processing_activities(),
        "contact": "/api/v1/privacy/contact",
        "as_of": _as_of(),
        "note": (
            "Stub disclosure for auditors and operators — register_kind remains "
            "article_30_stub. Schema v3 names every third-party AI processor "
            "reachable from code (not only the OCR pair), carries "
            "retention_posture / retains_content so a persistent transfer is "
            "distinguishable from transient processing, and marks unestablished "
            "regions and transfer mechanisms as unknown instead of guessing. "
            "Includes roles_and_contacts (Art. 30 A/B/P1 pointers), "
            "purpose / data_subject_categories, a general "
            "technical_organisational_measures block for Art. 30(1)(g), "
            "and international_transfers for Art. 30(1)(e) readability; link "
            "signed DPAs and complete DPO §9 before treating as full Art. 30 "
            "ROPA. EA-02 is not claimed closed; AI vendor DPAs remain pending; "
            "DPO identity is not invented. Each activity carries its documentary "
            "sources and a controller-review status; those fields do not make this a "
            "completed controller ROPA."
        ),
    }
