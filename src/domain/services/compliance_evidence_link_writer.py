"""The one place compliance evidence links are written.

Wave 2 PR-C, first step of the CEL sole-writer consolidation.

Why consolidate
---------------
``compliance_evidence_links`` is the table the Standards matrix reads to decide
whether a clause is covered, and it accumulated five independent writers, each
with its own idea of the rules. Two of those rules are not optional:

1. **D15 confirmer hygiene.** A non-manual rewrite of an existing link must clear
   ``confirmed_by_id`` / ``confirmed_at``, because that stamp attested to
   different content. A writer that forgets leaves a human's name against text
   they never saw.
2. **Version pinning.** A ``document`` link must be pinned to the library version
   it was written against (ADR-0021 P0), or the evidence silently follows the
   document as it changes.

Every writer that gets those wrong is a way to make the matrix lie. Routing them
through one function makes the rules testable in one place instead of five.

Scope of this step
------------------
This module is behaviour-preserving: it is the logic that was inline in
``POST /compliance/evidence/link`` and ``DELETE /compliance/evidence/link/{id}``,
moved without change. Governed-knowledge ingest (PR-E4) and Audit Builder Map
mirrors (PR-E5) now also write through :func:`apply_ingest_mapping`. The remaining
writers are listed in :data:`REMAINING_CEL_WRITERS` and are follow-up work — each
one needs its own reading, and doing them all here would make this change
unreviewable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceCoverKind,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
)

logger = logging.getLogger(__name__)

#: CEL writers still outside this module, with what each one needs before it can
#: be routed through here. Recorded rather than silently left, so the remaining
#: consolidation is a visible list and not folklore.
REMAINING_CEL_WRITERS: dict[str, str] = {
    "src/domain/services/external_audit_promotion_service.py": (
        "Two write sites (promotion of external audit findings and of their "
        "clause coverage). Needs the promotion transaction boundary checked "
        "before it can share this function's flush behaviour."
    ),
    "src/domain/services/audit_service.py": (
        "Listed as a leftover constructor site. Confirm there is still a live "
        "ComplianceEvidenceLink construct in audit completion before routing; "
        "do not drop this entry without a proof test."
    ),
}


@dataclass
class LinkWriteResult:
    """What one upsert did, for callers that report counts."""

    links: list[ComplianceEvidenceLink]
    created: int
    updated: int

    @property
    def total(self) -> int:
        return len(self.links)


async def upsert_evidence_links(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    entity_type: str,
    entity_id: str,
    clause_ids: Sequence[str],
    cover_kind: EvidenceCoverKind,
    link_method: EvidenceLinkMethod,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    confidence: Optional[float] = None,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    commit: bool = True,
) -> LinkWriteResult:
    """Create or update one link per clause for a single entity.

    Idempotent per ``(tenant, entity_type, entity_id, clause_id, cover_kind)``,
    which is the live unique key on the table: calling twice with the same
    arguments updates the same rows rather than duplicating them.

    ``commit`` is exposed so a caller already inside a transaction can hand the
    commit boundary back to itself. It defaults to True because the route that
    owns this operation today owns the transaction too.
    """
    requested = [str(clause_id) for clause_id in clause_ids]
    if not requested:
        return LinkWriteResult(links=[], created=0, updated=0)

    existing_result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.entity_type == entity_type,
            ComplianceEvidenceLink.entity_id == entity_id,
            ComplianceEvidenceLink.clause_id.in_(requested),
            ComplianceEvidenceLink.cover_kind == cover_kind,
        )
    )
    existing_by_clause = {link.clause_id: link for link in existing_result.scalars().all()}

    written: list[ComplianceEvidenceLink] = []
    created = 0
    updated = 0
    for clause_id in requested:
        link = existing_by_clause.get(clause_id)
        if link is None:
            link = ComplianceEvidenceLink(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                clause_id=clause_id,
                cover_kind=cover_kind,
                created_by_id=actor_id,
                created_by_email=actor_email,
            )
            db.add(link)
            created += 1
        else:
            updated += 1

        link.linked_by = link_method
        link.confidence = confidence
        link.title = title
        link.notes = notes
        link.cover_kind = cover_kind

        if link_method == EvidenceLinkMethod.MANUAL:
            # Manual create lands as confirmed (effective_status) — stamp confirmer.
            link.status = EvidenceLinkStatus.CONFIRMED
            link.auto_applied = False
            link.confirmed_by_id = actor_id
            link.confirmed_at = datetime.now(timezone.utc)
        else:
            # D15: a non-manual rewrite of an existing link must not keep the
            # earlier human confirmer — that stamp attested to different content.
            link.confirmed_by_id = None
            link.confirmed_at = None

        if entity_type == "document":
            from src.domain.services.cel_version_pin import pin_evidence_link_document_version

            await pin_evidence_link_document_version(db, link, tenant_id=tenant_id)

        written.append(link)

    if commit:
        await db.commit()
        for link in written:
            await db.refresh(link)

    return LinkWriteResult(links=written, created=created, updated=updated)


@dataclass
class LinkCreateIfAbsentResult:
    """Create-only write outcome — existing rows are reported, never rewritten."""

    created: list[ComplianceEvidenceLink]
    existing: list[ComplianceEvidenceLink]


async def create_evidence_links_if_absent(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    entity_type: str,
    entity_id: str,
    clause_ids: Sequence[str],
    cover_kind: EvidenceCoverKind,
    link_method: EvidenceLinkMethod,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    confidence: Optional[float] = None,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    signal_type: Optional[str] = None,
    status: Optional[EvidenceLinkStatus] = None,
    auto_applied: Optional[bool] = None,
    commit: bool = True,
) -> LinkCreateIfAbsentResult:
    """Create CEL rows only when no live row exists for the unique key.

    Unlike :func:`upsert_evidence_links`, this never rewrites ``title``,
    ``notes``, ``confidence``, or confirmer stamps on an existing row. EXACT
    share (Wave 2 PR-D) needs that guarantee so a share cannot put a different
    human's name against content they never reviewed (D15).

    Concurrent creates that hit ``ux_cel_tenant_entity_clause_cover_live`` are
    classified as ``existing`` after a re-read, not surfaced as 500s.
    """
    requested = [str(clause_id) for clause_id in clause_ids]
    if not requested:
        return LinkCreateIfAbsentResult(created=[], existing=[])

    existing_result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.entity_type == entity_type,
            ComplianceEvidenceLink.entity_id == entity_id,
            ComplianceEvidenceLink.clause_id.in_(requested),
            ComplianceEvidenceLink.cover_kind == cover_kind,
        )
    )
    existing_by_clause = {link.clause_id: link for link in existing_result.scalars().all()}

    created: list[ComplianceEvidenceLink] = []
    existing: list[ComplianceEvidenceLink] = []
    pending_create: list[ComplianceEvidenceLink] = []

    for clause_id in requested:
        link = existing_by_clause.get(clause_id)
        if link is not None:
            existing.append(link)
            continue

        link = ComplianceEvidenceLink(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            clause_id=clause_id,
            cover_kind=cover_kind,
            created_by_id=actor_id,
            created_by_email=actor_email,
        )
        link.linked_by = link_method
        link.confidence = confidence
        link.title = title
        link.notes = notes
        if signal_type is not None:
            link.signal_type = signal_type

        if status is not None:
            link.status = status
            link.auto_applied = bool(auto_applied) if auto_applied is not None else False
            if status == EvidenceLinkStatus.CONFIRMED:
                link.confirmed_by_id = actor_id
                link.confirmed_at = datetime.now(timezone.utc)
            else:
                link.confirmed_by_id = None
                link.confirmed_at = None
        elif link_method == EvidenceLinkMethod.MANUAL:
            link.status = EvidenceLinkStatus.CONFIRMED
            link.auto_applied = False
            link.confirmed_by_id = actor_id
            link.confirmed_at = datetime.now(timezone.utc)
        else:
            link.confirmed_by_id = None
            link.confirmed_at = None
            if auto_applied is not None:
                link.auto_applied = bool(auto_applied)

        if entity_type == "document":
            from src.domain.services.cel_version_pin import pin_evidence_link_document_version

            await pin_evidence_link_document_version(db, link, tenant_id=tenant_id)

        db.add(link)
        pending_create.append(link)

    if not pending_create:
        return LinkCreateIfAbsentResult(created=[], existing=existing)

    try:
        if commit:
            await db.commit()
        else:
            await db.flush()
        for link in pending_create:
            await db.refresh(link)
            created.append(link)
    except IntegrityError:
        await db.rollback()
        # A concurrent writer won the unique index. Re-read and classify every
        # requested clause as existing when a live row is present.
        re_read = await db.execute(
            select(ComplianceEvidenceLink).where(
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == entity_type,
                ComplianceEvidenceLink.entity_id == entity_id,
                ComplianceEvidenceLink.clause_id.in_(requested),
                ComplianceEvidenceLink.cover_kind == cover_kind,
            )
        )
        live = list(re_read.scalars().all())
        return LinkCreateIfAbsentResult(created=[], existing=live)

    return LinkCreateIfAbsentResult(created=created, existing=existing)


def _is_human_confirmed(link: ComplianceEvidenceLink) -> bool:
    if getattr(link, "confirmed_by_id", None) is not None:
        return True
    linked_by = getattr(link, "linked_by", None)
    value = str(getattr(linked_by, "value", linked_by) or "").strip().lower()
    return value == EvidenceLinkMethod.MANUAL.value


async def apply_ingest_mapping(
    db: AsyncSession,
    *,
    tenant_id: int,
    entity_type: str,
    entity_id: str,
    clause_id: str,
    status: EvidenceLinkStatus,
    auto_applied: bool,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    scheme: Optional[str] = None,
    confidence: Optional[float] = None,
    rationale: Optional[str] = None,
    title: Optional[str] = None,
    signal_type: Optional[str] = None,
    cover_kind: EvidenceCoverKind = EvidenceCoverKind.EVIDENCES,
    commit: bool = False,
) -> tuple[ComplianceEvidenceLink, bool]:
    """Write one governed-knowledge mapping through the sole CEL writer.

    PR-E gate already decided ``status`` / ``auto_applied``. This function does
    not call ``evaluate()``. Human confirmer stamps on an *existing* MANUAL /
    confirmed row are preserved (refresh confidence/rationale only). A newly
    created row is never treated as human-confirmed.

    ``commit`` defaults False so ingest stays inside the caller's transaction.
    """
    existing_result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.entity_type == entity_type,
            ComplianceEvidenceLink.entity_id == entity_id,
            ComplianceEvidenceLink.clause_id == clause_id,
            ComplianceEvidenceLink.cover_kind == cover_kind,
        )
    )
    existing = existing_result.scalar_one_or_none()
    is_new = existing is None
    if existing is None:
        link = ComplianceEvidenceLink(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            clause_id=clause_id,
            cover_kind=cover_kind,
            created_by_id=actor_id,
            created_by_email=actor_email,
        )
        db.add(link)
    else:
        link = existing

    human_preserved = (not is_new) and _is_human_confirmed(link)
    if human_preserved:
        link.scheme = scheme
        link.confidence = confidence
        link.rationale = rationale
        if title and not link.title:
            link.title = title
    else:
        link.scheme = scheme
        link.confidence = confidence
        link.rationale = rationale
        link.title = title
        link.status = status
        link.auto_applied = auto_applied
        link.linked_by = EvidenceLinkMethod.AI
        if auto_applied or status != EvidenceLinkStatus.CONFIRMED:
            link.confirmed_by_id = None
            link.confirmed_at = None

    if signal_type is not None:
        link.signal_type = signal_type
    elif entity_type == "document" and not link.signal_type:
        link.signal_type = "evidence"

    if entity_type == "document":
        from src.domain.services.cel_version_pin import pin_evidence_link_document_version

        await pin_evidence_link_document_version(db, link, tenant_id=tenant_id)

    if commit:
        await db.commit()
        await db.refresh(link)
    return link, human_preserved


async def soft_delete_evidence_link(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    link_id: int,
    commit: bool = True,
) -> Optional[ComplianceEvidenceLink]:
    """Soft-delete one link within a tenant. Returns None when there is none live.

    Soft delete rather than delete: the live unique index and every read path
    filter on ``deleted_at IS NULL``, and an audit pack that once cited a link
    should still be able to explain where it went.
    """
    result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.id == link_id,
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.tenant_id == tenant_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        return None

    link.deleted_at = datetime.now(timezone.utc)
    if commit:
        await db.commit()
    return link


def remaining_writer_report() -> list[dict[str, Any]]:
    """The consolidation backlog, for the PR body and follow-up tracking."""
    return [{"path": path, "blocked_on": reason} for path, reason in sorted(REMAINING_CEL_WRITERS.items())]
