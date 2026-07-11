"""Public privacy disclosure endpoints (Path-to-10 S15).

Provides machine-readable privacy contact details and data-lifecycle
capability flags without requiring authentication.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/privacy", tags=["Privacy"])

_DEFAULT_SECURITY_EMAIL = "security@plantexpand.com"
_DEFAULT_PRIVACY_EMAIL = "privacy@plantexpand.com"


def _security_email() -> str:
    return (os.getenv("SECURITY_CONTACT_EMAIL") or _DEFAULT_SECURITY_EMAIL).strip()


def _privacy_email() -> str:
    return (os.getenv("PRIVACY_CONTACT_EMAIL") or _DEFAULT_PRIVACY_EMAIL).strip()


@router.get("/contact")
async def privacy_contact() -> dict[str, Any]:
    """Public privacy / security contact and lifecycle capability flags.

    Surfaces RFC 9116 security.txt pointers plus documented soft-delete /
    legal-hold support on evidence assets (C4-adjacent attachments).
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
        "dpia": {
            "ocr_ai_import": "docs/compliance/dpia-ocr-ai-import.md",
            "incidents": "docs/privacy/dpia-incidents.md",
            "checklist": "docs/privacy/dpia-checklist.md",
            "governance_link": "docs/governance/privacy-ocr-ai-dpia.md",
        },
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
        "as_of": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
