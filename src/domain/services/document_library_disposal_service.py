"""Retention disposal queue for Governance Library documents (Wave W5).

The queue is intentionally conservative: it only lists inactive lifecycle
documents whose explicit ``retention_until`` date has passed. Category
retention rules remain visible as provenance, but are not parsed into an
automated deletion date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document
from src.domain.models.document_campaign import DocumentCampaign
from src.domain.models.document_control import ControlledDocument
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus
from src.domain.models.governed_knowledge import DocumentDiscussionThread, DocumentQuizDraft
from src.infrastructure.storage import storage_service

DISPOSAL_ELIGIBLE_STATUSES = (
    DocumentStatus.ARCHIVED,
    DocumentStatus.OBSOLETE,
    DocumentStatus.RETIRED,
    DocumentStatus.SUPERSEDED,
)


@dataclass(frozen=True)
class DisposalCandidate:
    """A document eligible for review or enabled execution."""

    document_id: int
    reference_number: str | None
    pel_doc_ref: str | None
    title: str
    status: str
    retention_until: datetime
    category_retention_rule: str | None


def disposal_eligibility_reason(document: Document, as_of: datetime) -> str | None:
    """Return a stable exclusion reason, or ``None`` when disposal is allowed."""
    retention_until = getattr(document, "retention_until", None)
    if retention_until is None:
        return "retention_until_missing"
    if retention_until > as_of:
        return "retention_not_due"
    status = getattr(document, "status", None)
    status_value = getattr(status, "value", str(status))
    eligible_values = {item.value for item in DISPOSAL_ELIGIBLE_STATUSES}
    if status_value not in eligible_values:
        return "lifecycle_not_disposable"
    return None


def _candidate_from_row(document: Document, retention_rule: str | None) -> DisposalCandidate:
    status = getattr(document.status, "value", document.status)
    return DisposalCandidate(
        document_id=document.id,
        reference_number=getattr(document, "reference_number", None),
        pel_doc_ref=getattr(document, "pel_doc_ref", None),
        title=document.title,
        status=str(status),
        retention_until=document.retention_until,
        category_retention_rule=retention_rule,
    )


def _has_no_governance_dependants():
    """SQL predicates that prevent disposal from severing governance provenance."""
    return (
        ~exists(select(DocumentCampaign.id).where(DocumentCampaign.document_id == Document.id)),
        ~exists(select(ControlledDocument.id).where(ControlledDocument.library_document_id == Document.id)),
        ~exists(select(DocumentDiscussionThread.id).where(DocumentDiscussionThread.document_id == Document.id)),
        ~exists(select(DocumentQuizDraft.id).where(DocumentQuizDraft.document_id == Document.id)),
    )


async def list_disposal_candidates(
    db: AsyncSession,
    *,
    tenant_id: int,
    as_of: datetime | None = None,
    limit: int = 100,
) -> list[DisposalCandidate]:
    """List tenant-scoped, retention-due inactive documents without mutating data."""
    as_of = as_of or datetime.now(timezone.utc)
    stmt = (
        select(Document, DocumentCategory.retention_rule)
        .outerjoin(DocumentCategory, Document.category_id == DocumentCategory.id)
        .where(
            Document.tenant_id == tenant_id,
            Document.is_active.is_(True),
            Document.retention_until.is_not(None),
            Document.retention_until <= as_of,
            Document.status.in_(DISPOSAL_ELIGIBLE_STATUSES),
            *_has_no_governance_dependants(),
        )
        .order_by(Document.retention_until.asc(), Document.id.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_candidate_from_row(document, retention_rule) for document, retention_rule in result.all()]


async def execute_disposal(
    db: AsyncSession,
    *,
    tenant_id: int,
    document_ids: Iterable[int],
    as_of: datetime | None = None,
) -> list[int]:
    """Hard-delete explicitly selected, currently eligible documents and blobs."""
    requested_ids = sorted(set(document_ids))
    if not requested_ids:
        return []

    as_of = as_of or datetime.now(timezone.utc)
    stmt = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.id.in_(requested_ids),
        *_has_no_governance_dependants(),
    )
    result = await db.execute(stmt)
    documents = {document.id: document for document in result.scalars().all()}

    disposed_documents: list[Document] = []
    for document_id in requested_ids:
        document = documents.get(document_id)
        if document is None or disposal_eligibility_reason(document, as_of) is not None:
            continue
        await db.delete(document)
        disposed_documents.append(document)

    # Flush before deleting blobs so foreign-key restrictions keep both the
    # document row and object intact when provenance still references it.
    await db.flush()
    try:
        for document in disposed_documents:
            await storage_service().delete(document.file_path)
    except Exception:
        await db.rollback()
        raise
    await db.commit()
    return [document.id for document in disposed_documents]
