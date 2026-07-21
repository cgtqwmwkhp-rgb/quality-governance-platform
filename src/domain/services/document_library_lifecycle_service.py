"""Governance Library Wave W1 — submit / approve / reject lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, StateTransitionError
from src.domain.models.document import Document, DocumentVersion
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_library_filing_service import (
    compute_retention_until,
    supersede_prior_approved_by_pel_doc_ref,
)
from src.domain.services.document_version_service import assert_version_mutable, version_is_immutable


async def submit_for_review(db: AsyncSession, document: Document) -> Document:
    """draft (or indexed) → under_review."""
    status = document.status
    if status not in {DocumentStatus.DRAFT, DocumentStatus.INDEXED, DocumentStatus.REJECTED}:
        raise StateTransitionError(
            f"Cannot submit document in status '{status.value if hasattr(status, 'value') else status}'"
        )
    if document.category_id is None:
        raise BadRequestError("Governance submit requires category_id (filed document)")

    document.status = DocumentStatus.UNDER_REVIEW
    document.reviewed_at = None
    document.review_notes = None
    await db.flush()
    return document


async def reject_review(
    db: AsyncSession,
    document: Document,
    *,
    reviewer_id: int,
    review_notes: str | None = None,
) -> Document:
    """under_review → draft."""
    if document.status != DocumentStatus.UNDER_REVIEW:
        raise StateTransitionError("Only documents under review can be rejected")

    document.status = DocumentStatus.DRAFT
    document.reviewed_by_id = reviewer_id
    document.reviewed_at = datetime.now(timezone.utc)
    document.review_notes = review_notes
    await db.flush()
    return document


async def approve_document(
    db: AsyncSession,
    document: Document,
    *,
    approved_by_id: int,
    version_id: int | None = None,
) -> DocumentVersion:
    """under_review → approved; supersede prior approved rows sharing pel_doc_ref."""
    if document.status != DocumentStatus.UNDER_REVIEW:
        raise StateTransitionError("Only documents under review can be approved")
    if document.created_by_id is not None and document.created_by_id == approved_by_id:
        raise BadRequestError("Self-approval is not permitted")

    if version_id is not None:
        version = await db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.id == version_id,
                DocumentVersion.document_id == document.id,
                DocumentVersion.tenant_id == document.tenant_id,
            )
        )
    else:
        version = await db.scalar(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.tenant_id == document.tenant_id,
                DocumentVersion.status == "draft",
                DocumentVersion.is_immutable.is_(False),
            )
            .order_by(DocumentVersion.created_at.desc())
            .limit(1)
        )

    if version is None:
        raise BadRequestError("No draft version available to approve")

    assert_version_mutable(version.status, version.is_immutable)

    prior_published = (
        (
            await db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.tenant_id == document.tenant_id,
                    DocumentVersion.status.in_(("published", "approved")),
                    DocumentVersion.id != version.id,
                )
            )
        )
        .scalars()
        .all()
    )

    now = datetime.now(timezone.utc)
    for prior in prior_published:
        prior.status = "superseded"
        prior.is_immutable = True

    version.status = "approved"
    version.is_immutable = True
    version.published_at = now
    version.published_by_id = approved_by_id

    document.version = version.version_number
    document.file_name = version.file_name
    document.file_path = version.file_path
    document.file_size = version.file_size
    document.status = DocumentStatus.APPROVED
    document.reviewed_by_id = approved_by_id
    document.reviewed_at = now

    if document.pel_doc_ref:
        await supersede_prior_approved_by_pel_doc_ref(
            db,
            tenant_id=document.tenant_id,
            pel_doc_ref=document.pel_doc_ref,
            current_document_id=document.id,
        )

    if document.category_id is not None:
        category = await db.get(DocumentCategory, document.category_id)
        if category is not None:
            document.retention_until = compute_retention_until(category, now)

    await db.flush()
    return version
