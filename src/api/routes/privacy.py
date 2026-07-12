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
    """Stub Article 30 register rows (high-level; not a full ROPA)."""
    return [
        {
            "activity_id": "user-accounts",
            "name": "User account administration",
            "lawful_basis": "legitimate_interest",
            "data_categories": ["email", "name", "role"],
            "retention_days": DEFAULT_RETENTION_POLICIES["users_deleted"].retention_days,
            "retention_note": "Account lifetime + users_deleted horizon post-deactivation",
            "storage": "postgresql",
        },
        {
            "activity_id": "incidents",
            "name": "Incident / H&S reporting",
            "lawful_basis": "legal_obligation",
            "data_categories": ["description", "location", "severity", "injury_details"],
            "retention_days": DEFAULT_RETENTION_POLICIES["incidents"].retention_days,
            "storage": "postgresql",
        },
        {
            "activity_id": "audit-findings",
            "name": "Audit findings and evidence",
            "lawful_basis": "legitimate_interest",
            "data_categories": ["finding_text", "evidence_references"],
            "retention_days": DEFAULT_RETENTION_POLICIES["audit_runs"].retention_days,
            "storage": "postgresql_and_azure_blob",
        },
        {
            "activity_id": "ocr-ai-import",
            "name": "External audit OCR / AI import",
            "lawful_basis": "legitimate_interest",
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
            "lawful_basis": "legitimate_interest",
            "data_categories": ["login_times", "ip_addresses", "tenant_id", "user_id"],
            "retention_days": DEFAULT_RETENTION_POLICIES["session_logs"].retention_days,
            "storage": "structured_logs_and_log_analytics",
        },
        {
            "activity_id": "complaints",
            "name": "Complaints / grievance handling",
            "lawful_basis": "legitimate_interest",
            "data_categories": ["complaint_text", "complainant_contact", "outcome"],
            "retention_days": DEFAULT_RETENTION_POLICIES["complaints"].retention_days,
            "storage": "postgresql",
        },
        {
            "activity_id": "near-misses",
            "name": "Near-miss / hazard reporting",
            "lawful_basis": "legitimate_interest",
            "data_categories": ["description", "location", "reporter"],
            "retention_days": DEFAULT_RETENTION_POLICIES["near_misses"].retention_days,
            "storage": "postgresql",
        },
        {
            "activity_id": "capa",
            "name": "Corrective and preventive actions (CAPA)",
            "lawful_basis": "legitimate_interest",
            "data_categories": ["action_text", "owner", "linked_finding_refs"],
            "retention_days": DEFAULT_RETENTION_POLICIES["audit_runs"].retention_days,
            "retention_note": "Aligned to audit_runs horizon pending discrete CAPA retention key",
            "storage": "postgresql",
        },
        {
            "activity_id": "risk-register",
            "name": "Enterprise / operational risk register",
            "lawful_basis": "legitimate_interest",
            "data_categories": ["risk_description", "owner", "controls"],
            "retention_days": DEFAULT_RETENTION_POLICIES["audit_runs"].retention_days,
            "retention_note": "Aligned to audit_runs horizon pending discrete risk retention key",
            "storage": "postgresql",
        },
        {
            "activity_id": "rta",
            "name": "Road traffic accident (RTA) records",
            "lawful_basis": "legitimate_interest",
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
        "subprocessors": _subprocessors(),
        "activities": _processing_activities(),
        "contact": "/api/v1/privacy/contact",
        "as_of": _as_of(),
        "note": (
            "Stub disclosure for auditors and operators — register_kind remains "
            "article_30_stub. Activity rows expanded for Preferred S15 readability; "
            "link signed DPAs and complete DPO §9 before treating as full Art. 30 ROPA."
        ),
    }
