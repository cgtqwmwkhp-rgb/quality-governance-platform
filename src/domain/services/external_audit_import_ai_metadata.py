"""Path-to-10 S1: apply AI-extracted audit metadata onto import jobs.

Canonical helper for persisting organization / auditor / certificate fields from
a completed AI analysis result onto ``ExternalAuditImportJob`` + provenance.
``ExternalAuditImportService`` keeps a thin compatibility wrapper.
"""

from __future__ import annotations

from datetime import datetime, timezone


def apply_ai_metadata_to_job(job: object, ai_result: object | None) -> None:
    """Persist AI-extracted audit metadata onto the job and provenance.

    No-op when ``ai_result`` is missing or ``provider_status`` is not
    ``completed``. Does not invent metadata — only copies truthy attributes.
    """
    if not ai_result or getattr(ai_result, "provider_status", None) != "completed":
        return

    job.organization_name = getattr(ai_result, "organization_name", None) or job.organization_name
    job.auditor_name = getattr(ai_result, "auditor_name", None) or job.auditor_name
    job.audit_type = getattr(ai_result, "audit_type", None) or job.audit_type
    job.certificate_number = getattr(ai_result, "certificate_number", None) or job.certificate_number
    job.audit_scope = getattr(ai_result, "audit_scope", None) or job.audit_scope
    next_audit_date = getattr(ai_result, "next_audit_date", None)
    if next_audit_date:
        try:
            job.next_audit_date = datetime.strptime(str(next_audit_date)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass

    meta_keys = (
        "organization_name",
        "auditor_name",
        "audit_type",
        "certificate_number",
        "audit_scope",
        "next_audit_date",
        "site_name",
        "site_address",
    )
    prov = dict(getattr(job, "provenance_json", None) or {})
    for key in meta_keys:
        val = getattr(ai_result, key, None)
        if val:
            prov[key] = val
    job.provenance_json = prov


__all__ = [
    "apply_ai_metadata_to_job",
]
