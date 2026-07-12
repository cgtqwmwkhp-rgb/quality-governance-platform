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

from src.core.retention_config import DEFAULT_RETENTION_POLICIES

router = APIRouter(prefix="/privacy", tags=["Privacy"])

_DEFAULT_SECURITY_EMAIL = "security@plantexpand.com"
_DEFAULT_PRIVACY_EMAIL = "privacy@plantexpand.com"

# Machine-readable DPIA close-out status (docs/compliance/dpia-quality-governance-platform.md).
# Engineering must not flip to "signed" until Section 9 is completed by the DPO.
_DPIA_STATUS = "pending_dpo_signoff"
_DPIA_DOC = "docs/compliance/dpia-quality-governance-platform.md"


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
        "matter_level_legal_hold_schema": False,
        "purge_schedule": "daily 02:00 UTC (Celery Beat run-data-retention)",
        "entity_horizons_days": {
            entity: policy.retention_days for entity, policy in DEFAULT_RETENTION_POLICIES.items()
        },
        "note": (
            "Horizons mirror DEFAULT_RETENTION_POLICIES; soft-delete-first is coded. "
            "Matter-level legal-hold columns are not yet schema SSOT — see retention policy §7a."
        ),
    }


def _dpia_disclosure() -> dict[str, Any]:
    """DPIA artifact pointers plus live close-out status field."""
    return {
        "status": _DPIA_STATUS,
        "status_doc": _DPIA_DOC,
        "platform": _DPIA_DOC,
        "ocr_ai_import": "docs/compliance/dpia-ocr-ai-import.md",
        "incidents": "docs/privacy/dpia-incidents.md",
        "checklist": "docs/privacy/dpia-checklist.md",
        "attestation_pack": "docs/compliance/s15-dpia-art30-attestation-pack.md",
        "article_30_checklist": "docs/compliance/article-30-ropa-checklist.md",
        "governance_link": "docs/governance/privacy-ocr-ai-dpia.md",
        "note": (
            "status=pending_dpo_signoff until Section 9 of the platform DPIA is signed by the DPO; "
            "unsigned attestation pack + Art. 30 checklist are ready-for-signoff only — "
            "no DPO signature is claimed here."
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
            "optional_ai_keys_off_by_default",
        ],
        "note": (
            "General Art. 30(1)(g) description for auditor readability only. "
            "Not a substitute for EA-02 external penetration testing; "
            "DPO §9 / EA-03 remain unsigned."
        ),
    }


def _international_transfers() -> dict[str, Any]:
    """Art. 30(1)(e) international transfers / safeguards summary (unsigned stub).

    Mirrors GDPR §7 + subprocessor ``transfer_mechanism`` fields. Does **not**
    invent signed vendor DPAs or claim production AI transfers are approved.
    """
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
            "Optional AI subprocessors may involve vendor-managed regions and "
            "require SCC or UK IDTA via vendor DPA before production keys."
        ),
        "optional_ai_transfer_status": "pending_vendor_dpa_before_production_keys",
        "subprocessor_transfer_mechanisms": [
            {
                "name": sp["name"],
                "transfer_mechanism": sp["transfer_mechanism"],
                "optional": sp["optional"],
            }
            for sp in _subprocessors()
        ],
        "note": (
            "Art. 30(1)(e) readability only — unsigned stub. Does not invent "
            "signed vendor DPAs; does not flip dpia.status; does not close EA-03. "
            "Confirm SCC / UK IDTA for Mistral / Gemini before production AI keys."
        ),
    }


def _subprocessors() -> list[dict[str, Any]]:
    """Public sub-processor list (Art. 28 disclosure stub).

    Mirrors infrastructure + optional OCR/AI processors documented in
    docs/compliance/dpia-ocr-ai-import.md and gdpr-compliance.md §7.
    """
    return [
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
            "transfer_mechanism": "uk_eea_hosting",
            "optional": False,
            "dpa_doc": "docs/compliance/gdpr-compliance.md",
        },
        {
            "name": "Mistral AI",
            "role": "ai_ocr_processor",
            "purposes": ["ocr", "structured_extraction"],
            "regions": ["vendor_managed"],
            "transfer_mechanism": "scc_or_uk_idta_via_vendor_dpa",
            "optional": True,
            "enabled_when": "mistral API keys configured",
            "dpa_doc": "docs/compliance/dpia-ocr-ai-import.md",
        },
        {
            "name": "Google Gemini",
            "role": "ai_review_processor",
            "purposes": ["multimodal_review"],
            "regions": ["vendor_managed"],
            "transfer_mechanism": "scc_or_uk_idta_via_vendor_dpa",
            "optional": True,
            "enabled_when": "google_gemini_api_key configured",
            "dpa_doc": "docs/compliance/dpia-ocr-ai-import.md",
        },
    ]


def _processing_activities() -> list[dict[str, Any]]:
    """Stub Article 30 register rows (high-level; not a full ROPA).

    Additive ``purpose`` / ``data_subject_categories`` fields close Art. 30
    checklist gaps C/D for auditor readability — still ``article_30_stub``.
    """
    return [
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
            "subprocessors": ["Mistral AI", "Google Gemini"],
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
        "controller": "tenant_organisation",
        "processor_operator": "Plantexpand (QGP platform operator)",
        "policy_doc": "docs/compliance/gdpr-compliance.md",
        "dpia": {
            "status": _DPIA_STATUS,
            "status_doc": _DPIA_DOC,
            "attestation_pack": "docs/compliance/s15-dpia-art30-attestation-pack.md",
        },
        "ropa_checklist": "docs/compliance/article-30-ropa-checklist.md",
        "technical_organisational_measures": _technical_organisational_measures(),
        "international_transfers": _international_transfers(),
        "subprocessors": _subprocessors(),
        "activities": _processing_activities(),
        "contact": "/api/v1/privacy/contact",
        "as_of": _as_of(),
        "note": (
            "Stub disclosure for auditors and operators — register_kind remains "
            "article_30_stub. Includes purpose / data_subject_categories, a "
            "general technical_organisational_measures block for Art. 30(1)(g), "
            "and international_transfers for Art. 30(1)(e) readability; link "
            "signed DPAs and complete DPO §9 before treating as full Art. 30 "
            "ROPA. EA-02 is not claimed closed; AI vendor DPAs remain pending."
        ),
    }
