"""Governance Library Wave W3 — review pack open/close + horizons."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError, StateTransitionError
from src.domain.models.document import Document
from src.domain.models.library_review import (
    FindingDisposition,
    LibraryRegulatoryFinding,
    LibraryReviewPack,
    ReviewPackStatus,
)
from src.domain.services.library_horizon_adapter import get_horizon_provider

DEFAULT_WINDOW_DAYS = 90
ALLOWED_HORIZON_MONTHS = frozenset({3, 6, 12})

EMPTY_INTERNAL_INPUTS: dict[str, list[Any]] = {
    "new_docs": [],
    "dependencies": [],
    "incidents": [],
    "audits": [],
}


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def review_window_allows_open(
    review_date: Optional[datetime],
    *,
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> bool:
    """True when review_date is overdue or within ``window_days`` ahead."""
    if review_date is None:
        return False
    current = _as_utc(now or datetime.now(timezone.utc))
    due = _as_utc(review_date)
    days_until = int((due - current).total_seconds() // 86400)
    return days_until <= window_days


def stub_internal_inputs() -> dict[str, list[Any]]:
    """Thin stub for internal review inputs (deep joins deferred)."""
    return {key: list(value) for key, value in EMPTY_INTERNAL_INPUTS.items()}


async def _get_document(db: AsyncSession, *, tenant_id: int, document_id: int) -> Document:
    document = await db.scalar(select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id))
    if document is None:
        raise NotFoundError(f"Document {document_id} not found")
    return document


async def _get_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    pack_id: int,
    with_findings: bool = False,
) -> LibraryReviewPack:
    stmt = select(LibraryReviewPack).where(
        LibraryReviewPack.id == pack_id,
        LibraryReviewPack.tenant_id == tenant_id,
    )
    if with_findings:
        stmt = stmt.options(selectinload(LibraryReviewPack.findings))
    pack = await db.scalar(stmt)
    if pack is None:
        raise NotFoundError(f"Review pack {pack_id} not found")
    return pack


async def open_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    document_id: int,
    opened_by_id: int,
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[datetime] = None,
) -> LibraryReviewPack:
    """Open a review pack when the document is in the 90-day window or overdue."""
    document = await _get_document(db, tenant_id=tenant_id, document_id=document_id)
    current = _as_utc(now or datetime.now(timezone.utc))

    if not review_window_allows_open(document.review_date, now=current, window_days=window_days):
        raise BadRequestError(
            f"Document {document_id} is outside the {window_days}-day review window "
            "(review_date missing, or more than window_days ahead)"
        )

    existing = await db.scalar(
        select(LibraryReviewPack).where(
            LibraryReviewPack.tenant_id == tenant_id,
            LibraryReviewPack.document_id == document_id,
            LibraryReviewPack.status == ReviewPackStatus.OPEN,
        )
    )
    if existing is not None:
        raise ConflictError(f"Document {document_id} already has an open review pack ({existing.id})")

    review_date = _as_utc(document.review_date)  # type: ignore[arg-type]
    pack = LibraryReviewPack(
        tenant_id=tenant_id,
        document_id=document_id,
        status=ReviewPackStatus.OPEN,
        window_days=window_days,
        window_start=review_date - timedelta(days=window_days),
        window_end=review_date,
        opened_at=current,
        opened_by_id=opened_by_id,
        internal_inputs=stub_internal_inputs(),
    )
    db.add(pack)
    await db.flush()
    return pack


async def get_pack(db: AsyncSession, *, tenant_id: int, pack_id: int) -> LibraryReviewPack:
    return await _get_pack(db, tenant_id=tenant_id, pack_id=pack_id, with_findings=True)


async def list_packs(
    db: AsyncSession,
    *,
    tenant_id: int,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[LibraryReviewPack]:
    stmt = (
        select(LibraryReviewPack)
        .where(LibraryReviewPack.tenant_id == tenant_id)
        .order_by(LibraryReviewPack.opened_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(LibraryReviewPack.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_finding(
    db: AsyncSession,
    *,
    tenant_id: int,
    pack_id: int,
    finding_id: int,
) -> LibraryRegulatoryFinding:
    finding = await db.scalar(
        select(LibraryRegulatoryFinding).where(
            LibraryRegulatoryFinding.id == finding_id,
            LibraryRegulatoryFinding.pack_id == pack_id,
            LibraryRegulatoryFinding.tenant_id == tenant_id,
        )
    )
    if finding is None:
        raise NotFoundError(f"Finding {finding_id} not found on pack {pack_id}")
    return finding


async def confirm_finding(
    db: AsyncSession,
    *,
    tenant_id: int,
    pack_id: int,
    finding_id: int,
    user_id: int,
    notes: Optional[str] = None,
) -> LibraryRegulatoryFinding:
    pack = await _get_pack(db, tenant_id=tenant_id, pack_id=pack_id)
    if pack.status != ReviewPackStatus.OPEN:
        raise StateTransitionError("Cannot disposition findings on a closed pack")
    finding = await _get_finding(db, tenant_id=tenant_id, pack_id=pack_id, finding_id=finding_id)
    finding.disposition = FindingDisposition.CONFIRMED
    finding.dispositioned_by_id = user_id
    finding.dispositioned_at = datetime.now(timezone.utc)
    finding.disposition_notes = notes
    await db.flush()
    return finding


async def reject_finding(
    db: AsyncSession,
    *,
    tenant_id: int,
    pack_id: int,
    finding_id: int,
    user_id: int,
    notes: Optional[str] = None,
) -> LibraryRegulatoryFinding:
    pack = await _get_pack(db, tenant_id=tenant_id, pack_id=pack_id)
    if pack.status != ReviewPackStatus.OPEN:
        raise StateTransitionError("Cannot disposition findings on a closed pack")
    finding = await _get_finding(db, tenant_id=tenant_id, pack_id=pack_id, finding_id=finding_id)
    finding.disposition = FindingDisposition.REJECTED
    finding.dispositioned_by_id = user_id
    finding.dispositioned_at = datetime.now(timezone.utc)
    finding.disposition_notes = notes
    await db.flush()
    return finding


async def close_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    pack_id: int,
    closed_by_id: int,
) -> LibraryReviewPack:
    pack = await _get_pack(db, tenant_id=tenant_id, pack_id=pack_id, with_findings=True)
    if pack.status != ReviewPackStatus.OPEN:
        raise StateTransitionError("Pack is already closed")

    pending = [f for f in pack.findings if f.disposition == FindingDisposition.PENDING]
    if pending:
        raise StateTransitionError(f"Cannot close pack while {len(pending)} finding(s) remain pending")

    pack.status = ReviewPackStatus.CLOSED
    pack.closed_at = datetime.now(timezone.utc)
    pack.closed_by_id = closed_by_id
    await db.flush()
    return pack


async def run_horizon_scan(
    db: AsyncSession,
    *,
    tenant_id: int,
    pack_id: int,
    provider_name: Optional[str] = None,
) -> list[LibraryRegulatoryFinding]:
    """Run the configured horizon provider and persist pending findings."""
    pack = await _get_pack(db, tenant_id=tenant_id, pack_id=pack_id)
    if pack.status != ReviewPackStatus.OPEN:
        raise StateTransitionError("Cannot scan a closed pack")

    document = await _get_document(db, tenant_id=tenant_id, document_id=pack.document_id)
    provider = get_horizon_provider(provider_name)
    drafts = provider.scan(
        document_id=document.id,
        document_title=document.title or document.file_name or f"document-{document.id}",
        tenant_id=tenant_id,
    )

    created: list[LibraryRegulatoryFinding] = []
    for draft in drafts:
        finding = LibraryRegulatoryFinding(
            tenant_id=tenant_id,
            pack_id=pack.id,
            provider=draft.provider,
            external_id=draft.external_id,
            title=draft.title,
            summary=draft.summary,
            source_url=draft.source_url,
            raw_payload=draft.raw_payload,
            disposition=FindingDisposition.PENDING,
        )
        db.add(finding)
        created.append(finding)
    await db.flush()
    return created


async def horizons(
    db: AsyncSession,
    *,
    tenant_id: int,
    months: int = 3,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Bucket filed documents by ``review_date`` within the given month horizon."""
    if months not in ALLOWED_HORIZON_MONTHS:
        raise BadRequestError("months must be one of 3, 6, or 12")

    current = _as_utc(now or datetime.now(timezone.utc))
    horizon_end = current + timedelta(days=int(months * 30.4375))

    result = await db.execute(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.category_id.is_not(None),
            Document.review_date.is_not(None),
        )
    )
    documents = list(result.scalars().all())

    overdue_rows: list[dict[str, Any]] = []
    due_rows: list[dict[str, Any]] = []
    upcoming_rows: list[dict[str, Any]] = []

    for doc in documents:
        review_date = _as_utc(doc.review_date)  # type: ignore[arg-type]
        row = {
            "document_id": doc.id,
            "title": doc.title,
            "review_date": review_date.isoformat(),
            "pel_doc_ref": getattr(doc, "pel_doc_ref", None),
        }
        if review_date < current:
            overdue_rows.append(row)
        elif review_date <= horizon_end:
            days_until = int((review_date - current).total_seconds() // 86400)
            if days_until <= DEFAULT_WINDOW_DAYS:
                due_rows.append(row)
            else:
                upcoming_rows.append(row)

    return {
        "months": months,
        "as_of": current.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "counts": {
            "overdue": len(overdue_rows),
            "due": len(due_rows),
            "upcoming": len(upcoming_rows),
            "total": len(overdue_rows) + len(due_rows) + len(upcoming_rows),
        },
        "overdue": overdue_rows,
        "due": due_rows,
        "upcoming": upcoming_rows,
    }
