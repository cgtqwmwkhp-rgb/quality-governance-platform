"""Governance Library — submit / approve / reject (W1) and issue (W6 / NS-WF).

Every status move here goes through the Northern Star transition table in
`library_workflow`, which is projected from the authority pack rather than
re-typed, so an illegal move is refused in one place instead of by whichever
ad-hoc `if` a call site grew.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError
from src.domain.models.document import Document, DocumentVersion
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_library_filing_service import (
    apply_category_retention,
    supersede_prior_approved_by_pel_doc_ref,
)
from src.domain.services.document_version_service import assert_version_mutable, version_is_immutable
from src.domain.services.legal_hold_enforcement import assert_document_not_held
from src.domain.services.library_workflow import (
    assert_amendment_record_complete,
    assert_approver_is_not_version_author,
    assert_parent_named,
    assert_review_cycle_declared,
    assert_transition_allowed,
    assert_whole_number_version,
    has_confirmed_primary_parent,
)

# Version rows that already represent a live or historic issue.
_ISSUED_VERSION_STATUSES = ("published", "approved")


async def submit_for_review(db: AsyncSession, document: Document) -> Document:
    """draft (or indexed) → under_review."""
    assert_transition_allowed(
        document.status,
        DocumentStatus.UNDER_REVIEW,
        document_id=getattr(document, "id", None),
    )
    if document.category_id is None:
        raise BadRequestError("Governance submit requires category_id (filed document)")
    await assert_document_not_held(db, document, action="submitted for review")

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
    assert_transition_allowed(
        document.status,
        DocumentStatus.DRAFT,
        document_id=getattr(document, "id", None),
    )
    await assert_document_not_held(db, document, action="returned to draft")

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
    assert_transition_allowed(
        document.status,
        DocumentStatus.APPROVED,
        document_id=getattr(document, "id", None),
    )
    if document.created_by_id is not None and document.created_by_id == approved_by_id:
        raise BadRequestError("Self-approval is not permitted")
    await assert_document_not_held(db, document, action="approved")

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
    # R23 — the self-approval check above compares against whoever *filed* the
    # document; this compares against the author of the version being approved,
    # which is the leg the pack names and the one a revision can slip through.
    assert_approver_is_not_version_author(
        approver_id=approved_by_id,
        version_author_id=getattr(version, "created_by_id", None),
    )

    prior_published = (
        (
            await db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.tenant_id == document.tenant_id,
                    DocumentVersion.status.in_(_ISSUED_VERSION_STATUSES),
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
            superseded_at=now,
        )

    if document.category_id is not None:
        category = await db.get(DocumentCategory, document.category_id)
        if category is not None:
            # CUT-1 — the policy is copied onto the document, and only an
            # issue-anchored one gets a date now. A "Current + superseded N
            # years" rule starts its clock when this document is itself
            # superseded, not today; dating it from approval is what let a
            # document be disposed the day it stopped being current.
            apply_category_retention(document, category, issued_at=now)

    await db.flush()
    return version


async def issue_document(
    db: AsyncSession,
    document: Document,
    *,
    issued_by_id: int,
    version_id: int | None = None,
    review_cycle_months: int | None = None,
    review_cycle_basis: str | None = None,
) -> DocumentVersion:
    """Northern Star W6 / NS-WF: approved → issued, with the pack's issue blocks.

    This is the governed way a library document goes live. It is deliberately a
    separate transition from the legacy ``POST /documents/{id}/publish`` path,
    which still reaches ``PUBLISHED`` straight from a draft with no approval — see
    the Change Ledger; closing that path is a product decision, not a refactor.

    Refused unless, in this order: the move is legal (approved → issued only, so
    an unapproved document cannot be issued — R14's approval leg); no legal hold;
    an approved version row exists; its approver was not its author (R23); its
    number is a whole number (R22); its amendment row is complete and reconciles
    (R10/R11); the document states a review cycle and basis (R20); and a document
    below L1 names a parent (R07).

    No rendition is produced and none is claimed. R15 (level stamped into the
    footer by the rendering pipeline) is not implemented — there is no rendering
    pipeline — so "issued" here means the register says issued, not that a
    stamped PDF exists.
    """
    assert_transition_allowed(
        document.status,
        DocumentStatus.PUBLISHED,
        document_id=getattr(document, "id", None),
    )
    await assert_document_not_held(db, document, action="issued")

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
                DocumentVersion.status == "approved",
            )
            .order_by(DocumentVersion.published_at.desc().nulls_last(), DocumentVersion.id.desc())
            .limit(1)
        )

    if version is None or getattr(version, "status", None) != "approved":
        raise BadRequestError(
            "R14: only an approved version is issued. Approve the version first — "
            "a document is never put live straight from draft on this path.",
            details={"rule": "R14", "document_id": getattr(document, "id", None)},
        )

    assert_approver_is_not_version_author(
        approver_id=getattr(version, "published_by_id", None),
        version_author_id=getattr(version, "created_by_id", None),
    )
    assert_whole_number_version(version.version_number)
    assert_amendment_record_complete(
        change_notes=getattr(version, "change_notes", None),
        version_number=version.version_number,
        document_version=getattr(document, "version", None),
    )

    # R20 — the owner may state the cycle as part of issuing. It is only ever
    # written from an explicit value on the request; nothing derives one.
    if review_cycle_months is not None:
        document.review_cycle_months = int(review_cycle_months)
    if review_cycle_basis is not None:
        document.review_cycle_basis = review_cycle_basis
    assert_review_cycle_declared(
        review_cycle_months=getattr(document, "review_cycle_months", None),
        review_cycle_basis=getattr(document, "review_cycle_basis", None),
    )

    cascade_level = getattr(document, "cascade_level", None)
    assert_parent_named(
        cascade_level=cascade_level,
        has_primary_parent=(
            await has_confirmed_primary_parent(db, document)
            if cascade_level is not None and int(cascade_level) > 1
            else False
        ),
    )

    # R18 — the previous issue is superseded in the same transaction as the new
    # one, so "the same day" is not a nightly job that can miss.
    prior_issued = (
        (
            await db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.tenant_id == document.tenant_id,
                    DocumentVersion.status.in_(_ISSUED_VERSION_STATUSES),
                    DocumentVersion.id != version.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for prior in prior_issued:
        prior.status = "superseded"
        prior.is_immutable = True

    now = datetime.now(timezone.utc)
    version.status = "published"
    version.is_immutable = True
    # `published_at` / `published_by_id` hold the approval and are left alone —
    # overwriting them would record the issuer as the approver.
    version.issued_at = now
    version.issued_by_id = issued_by_id

    document.version = version.version_number
    document.file_name = version.file_name
    document.file_path = version.file_path
    document.file_size = version.file_size
    document.status = DocumentStatus.PUBLISHED

    if document.pel_doc_ref:
        await supersede_prior_approved_by_pel_doc_ref(
            db,
            tenant_id=document.tenant_id,
            pel_doc_ref=document.pel_doc_ref,
            current_document_id=document.id,
        )

    await db.flush()
    return version
