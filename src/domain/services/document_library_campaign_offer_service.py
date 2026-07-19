"""Governance Library Wave W4a — HSEQ approve → optional DocumentCampaign offer."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError
from src.domain.models.document import Document
from src.domain.models.document_campaign import CampaignStatus, DocumentCampaign
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_campaign_service import DocumentCampaignService
from src.domain.services.document_library_rbac import user_can_read_library_document

DEFAULT_DUE_WITHIN_DAYS = 14
UI_LABEL = "HSEQ reading campaign"


def _status_value(document: Document) -> str:
    status = document.status
    return status.value if hasattr(status, "value") else str(status)


def campaign_offer_eligibility(document: Document) -> tuple[bool, Optional[str]]:
    """Return (eligible, reason) for offering an HSEQ reading campaign."""
    if document.category_id is None:
        return False, "not_filed"
    if _status_value(document) != DocumentStatus.APPROVED.value:
        return False, "not_approved"
    access = (getattr(document, "access_level", None) or "all_staff").strip().lower()
    if access != "all_staff":
        return False, f"access_level_{access}"
    return True, None


def build_campaign_offer_payload(
    document: Document,
    *,
    existing_campaigns: list[DocumentCampaign] | None = None,
) -> dict[str, Any]:
    """Build the additive ``campaign_offer`` block for approve responses."""
    eligible, reason = campaign_offer_eligibility(document)
    existing = existing_campaigns or []
    active_id = next((c.id for c in existing if c.status == CampaignStatus.ACTIVE), None)
    draft_id = next((c.id for c in existing if c.status == CampaignStatus.DRAFT), None)
    title = (document.title or "Document").strip() or "Document"
    return {
        "eligible": eligible,
        "reason": reason,
        "document_id": document.id,
        "pel_doc_ref": getattr(document, "pel_doc_ref", None),
        "access_level": getattr(document, "access_level", None) or "all_staff",
        "is_statutory": bool(getattr(document, "is_statutory", False)),
        "suggested_title": f"Read & acknowledge: {title}",
        "default_audience": {"audience_type": "all_users"},
        "default_due_within_days": DEFAULT_DUE_WITHIN_DAYS,
        "require_sign": True,
        "require_quiz": False,
        "existing_active_campaign_id": active_id,
        "existing_draft_campaign_id": draft_id,
        "ui_label": UI_LABEL,
    }


async def build_campaign_offer_for_document(
    db: AsyncSession,
    *,
    tenant_id: int,
    document: Document,
) -> dict[str, Any]:
    service = DocumentCampaignService(db)
    campaigns = await service.list_campaigns_for_document(tenant_id=tenant_id, document_id=document.id)
    return build_campaign_offer_payload(document, existing_campaigns=campaigns)


async def offer_campaign_from_document(
    db: AsyncSession,
    *,
    tenant_id: int,
    document: Document,
    actor_id: int,
    actor: Any,
    title: Optional[str] = None,
    due_within_days: int = DEFAULT_DUE_WITHIN_DAYS,
    require_quiz: bool = False,
    require_sign: bool = True,
    audience_type: str = "all_users",
    launch: bool = False,
) -> dict[str, Any]:
    """Create a draft DocumentCampaign (optional launch) after HSEQ approve."""
    if not user_can_read_library_document(document, actor):
        raise BadRequestError("Document is not readable for campaign offer")

    eligible, reason = campaign_offer_eligibility(document)
    if not eligible:
        raise BadRequestError(f"Document is not eligible for HSEQ campaign offer ({reason})")

    service = DocumentCampaignService(db)
    existing = await service.list_campaigns_for_document(tenant_id=tenant_id, document_id=document.id)
    draft = next((c for c in existing if c.status == CampaignStatus.DRAFT), None)
    if draft is not None:
        return {
            "offered": False,
            "campaign_id": draft.id,
            "status": CampaignStatus.DRAFT.value,
            "launched": False,
            "assigned_count": 0,
            "reason": "draft_already_exists",
        }

    if audience_type != "all_users":
        raise BadRequestError("W4a offer supports audience_type=all_users only; refine in the HSEQ campaign panel")

    campaign_title = (title or "").strip() or f"Read & acknowledge: {(document.title or 'Document').strip()}"
    campaign = await service.create_campaign(
        tenant_id=tenant_id,
        created_by_id=actor_id,
        document_id=document.id,
        title=campaign_title,
        due_within_days=due_within_days,
        require_quiz=require_quiz,
        require_sign=require_sign,
        audience={"all_users": True},
    )

    if not launch:
        return {
            "offered": True,
            "campaign_id": campaign.id,
            "status": CampaignStatus.DRAFT.value,
            "launched": False,
            "assigned_count": 0,
            "reason": None,
        }

    launched = await service.launch_campaign(
        tenant_id=tenant_id,
        campaign_id=campaign.id,
        launched_by_id=actor_id,
    )
    return {
        "offered": True,
        "campaign_id": campaign.id,
        "status": CampaignStatus.ACTIVE.value,
        "launched": True,
        "assigned_count": int(launched.get("assigned_count") or launched.get("total_assigned") or 0),
        "reason": None,
    }


__all__ = [
    "DEFAULT_DUE_WITHIN_DAYS",
    "UI_LABEL",
    "build_campaign_offer_for_document",
    "build_campaign_offer_payload",
    "campaign_offer_eligibility",
    "offer_campaign_from_document",
]
