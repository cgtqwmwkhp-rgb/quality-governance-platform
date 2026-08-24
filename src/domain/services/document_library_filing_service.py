"""Governance Library Wave W1 — filing rules, ACL, retention, duplicate detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document import Document
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus
from src.domain.services.library_retention_policy import (
    RetentionAnchor,
    RetentionDecision,
    RetentionPolicy,
    policy_from_stored,
    resolve_retention_rule,
    retention_until_for,
)
from src.domain.services.library_rules import LIBRARY_ACCESS_LEVELS

if TYPE_CHECKING:
    from src.domain.models.user import User

_STATUTORY_TAXONOMY_PREFIXES = ("03.", "04.")
_APPROVED_STATUSES = (
    DocumentStatus.APPROVED,
    DocumentStatus.PUBLISHED,
    DocumentStatus.ACTIVE,
    DocumentStatus.INDEXED,
)
_TITLE_NORMALIZE_RE = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class DuplicateCandidate:
    document_id: int
    title: str
    reference_number: str
    pel_doc_ref: Optional[str]


@dataclass(frozen=True)
class FilingDefaults:
    access_level: str
    is_statutory: bool


def normalize_title(title: str) -> str:
    lowered = (title or "").lower()
    cleaned = _TITLE_NORMALIZE_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def is_statutory_taxonomy_id(taxonomy_id: str) -> bool:
    return taxonomy_id.startswith(_STATUTORY_TAXONOMY_PREFIXES)


def map_category_access(default_access: Optional[str]) -> str:
    """Category default → the one Library vocabulary, falling back to `all_staff`.

    The allowed set is imported from ``library_rules`` (which owns R26) rather
    than re-typed here: CUT-1 removed the second copy of these three literals so
    a vocabulary change has one place to land.
    """
    value = (default_access or "all_staff").strip().lower()
    if value in LIBRARY_ACCESS_LEVELS:
        return value
    return "all_staff"


def filing_defaults_for_category(category: DocumentCategory) -> FilingDefaults:
    return FilingDefaults(
        access_level=map_category_access(category.default_access),
        is_statutory=is_statutory_taxonomy_id(category.taxonomy_id),
    )


async def load_filing_category(db: AsyncSession, category_id: int) -> DocumentCategory:
    """Validate category_id is an active level-2 taxonomy row."""
    category = await db.get(DocumentCategory, category_id)
    if category is None:
        raise NotFoundError(f"Document category {category_id} not found")
    if category.level != 2:
        raise ValidationError("Filing requires a level-2 (subcategory) category_id")
    if not category.active:
        raise ValidationError(f"Category '{category.name}' is inactive and cannot accept new documents")
    return category


def titles_are_similar(left: str, right: str) -> bool:
    a = normalize_title(left)
    b = normalize_title(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return shorter in longer and len(shorter) >= max(8, int(len(longer) * 0.6))


async def find_duplicate_approved_candidates(
    db: AsyncSession,
    *,
    tenant_id: int,
    category_id: int,
    site_location_id: Optional[int],
    title: str,
    exclude_document_id: Optional[int] = None,
) -> list[DuplicateCandidate]:
    """Warn when an approved/published doc exists for same category+site+similar title."""
    stmt = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.category_id == category_id,
        Document.is_active.is_(True),
        Document.status.in_(_APPROVED_STATUSES),
    )
    if site_location_id is None:
        stmt = stmt.where(Document.site_location_id.is_(None))
    else:
        stmt = stmt.where(Document.site_location_id == site_location_id)
    if exclude_document_id is not None:
        stmt = stmt.where(Document.id != exclude_document_id)

    result = await db.execute(stmt)
    matches: list[DuplicateCandidate] = []
    for row in result.scalars().all():
        if titles_are_similar(title, row.title):
            matches.append(
                DuplicateCandidate(
                    document_id=row.id,
                    title=row.title,
                    reference_number=getattr(row, "reference_number", None) or f"DOC-{row.id}",
                    pel_doc_ref=getattr(row, "pel_doc_ref", None),
                )
            )
    return matches


def retention_policy_for_category(category: DocumentCategory) -> RetentionDecision:
    """CUT-1 — read the category's machine-readable retention, else its prose.

    Prefers the columns the CUT-1 migration projected onto the category, so a
    steward who resolves one of the fourteen unreadable rules by setting
    ``retention_years`` / ``retention_anchor`` is obeyed immediately without
    having to also rewrite the prose. Falls back to parsing ``retention_rule``
    for categories created outside the seed.
    """
    stored = policy_from_stored(
        retention_years=getattr(category, "retention_years", None),
        retention_anchor=getattr(category, "retention_anchor", None),
        retention_basis=getattr(category, "retention_rule", None),
    )
    if stored is not None:
        return RetentionDecision(stored, stored.anchor.value)
    return resolve_retention_rule(getattr(category, "retention_rule", None))


def compute_retention_until(category: DocumentCategory, anchor_date: datetime) -> Optional[datetime]:
    """Disposal date for this category's policy, measured from ``anchor_date``.

    Which date to pass is the caller's decision, because the taxonomy contains
    both kinds of rule: an issue-anchored ``"6 years"`` counts from approval,
    while ``"Current + superseded 6 years"`` counts from the day the document was
    superseded. ``approve_document`` therefore passes the approval date only for
    issue-anchored policies, and ``supersede_prior_approved_by_pel_doc_ref``
    passes the supersede date for supersede-anchored ones.

    Returns ``None`` for an event-anchored or indefinite policy, and for a rule
    the CUT-1 grammar refuses to read — none of those have a disposal date QGP
    can calculate, and inventing one feeds a queue that hard-deletes files.
    """
    decision = retention_policy_for_category(category)
    policy = decision.policy
    if policy is None or policy.anchor is RetentionAnchor.ISSUE:
        return retention_until_for(policy, issued_at=anchor_date)
    if policy.anchor is RetentionAnchor.SUPERSEDE:
        return retention_until_for(policy, superseded_at=anchor_date)
    return None


def apply_category_retention(document: Document, category: DocumentCategory, *, issued_at: datetime) -> None:
    """Copy the category's retention policy onto the document at file time (F-7 §2).

    After this the document answers for its own retention: the policy that was
    in force when it was filed is on the row, so a later taxonomy edit cannot
    silently re-date it. Only an issue-anchored policy gets a
    ``retention_until`` here — a supersede-anchored clock has not started yet.

    ``retention_until`` is *re-derived*, never left as it was. A document that is
    re-approved after its category moved from ``"6 years"`` to
    ``"Current + superseded 6 years"`` would otherwise keep the issue-anchored
    date the old rule produced, which is earlier than the new rule allows — the
    exact premature-disposal shape CUT-1 exists to close. Clearing it is the safe
    direction: no date means no disposal candidate.
    """
    decision = retention_policy_for_category(category)
    policy = decision.policy
    document.retention_years = policy.years if policy else None
    document.retention_anchor = policy.anchor.value if policy else None
    document.retention_basis = policy.basis if policy else (category.retention_rule or None)
    document.retention_until = (
        retention_until_for(policy, issued_at=issued_at)
        if policy is not None and policy.anchor is RetentionAnchor.ISSUE
        else None
    )


def _stored_policy(document: Document) -> Optional[RetentionPolicy]:
    return policy_from_stored(
        retention_years=getattr(document, "retention_years", None),
        retention_anchor=getattr(document, "retention_anchor", None),
        retention_basis=getattr(document, "retention_basis", None),
    )


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def supersede_retention_until(document: Document, superseded_at: datetime) -> Optional[datetime]:
    """The document's disposal date once it leaves the live set — read, not written.

    The Register row is the retention system of record (F-7 §2), so anything that
    needs to know when a document may be destroyed asks this rather than keeping
    its own clock. ``None`` means "not calculable", which is the keep direction:
    an event-anchored or indefinite policy, a rule the CUT-1 grammar refused, or a
    document that was filed before CUT-1 and carries no policy at all.

    Never earlier than the date already on the row. A legacy row filed before
    CUT-1 carries a ``retention_until`` computed from its approval date, which for
    a supersede-anchored rule is too early; taking the later of the two repairs it
    instead of honouring a date the governance rule never sanctioned.
    """
    current = _as_utc(getattr(document, "retention_until", None))
    policy = _stored_policy(document)
    if policy is None or policy.anchor is not RetentionAnchor.SUPERSEDE:
        return current
    candidate = retention_until_for(policy, superseded_at=_as_utc(superseded_at))
    if candidate is None:
        return current
    if current is None or candidate > current:
        return candidate
    return current


def apply_supersede_retention(document: Document, superseded_at: datetime) -> None:
    """Write the supersede-anchored clock onto the row as it leaves the live set.

    The only writer of ``retention_until`` on supersede. It writes exactly what
    :func:`supersede_retention_until` resolves, and only when that is later than
    the date already there — so a document is never made disposable sooner by
    being superseded, and a policy that cannot start a clock leaves the row alone.
    """
    resolved = supersede_retention_until(document, superseded_at)
    current = _as_utc(getattr(document, "retention_until", None))
    if resolved is not None and (current is None or resolved > current):
        document.retention_until = resolved


def assert_library_read_access(
    document: Document,
    user: User,
    *,
    taxonomy_id: str | None = None,
) -> None:
    """404-not-403: hide existence when ACL denies read (Wave W1/W2).

    Restricted categories (02.08 / 06.03 / 11.03) require
    ``document:restricted:{oh|driver|breach}`` (or ``admin:manage``).
    """
    from src.domain.services.document_library_rbac import user_can_read_library_document

    if user_can_read_library_document(document, user, taxonomy_id=taxonomy_id):
        return
    raise NotFoundError("Document not found")


async def supersede_prior_approved_by_pel_doc_ref(
    db: AsyncSession,
    *,
    tenant_id: int,
    pel_doc_ref: str,
    current_document_id: int,
    superseded_at: Optional[datetime] = None,
) -> list[int]:
    """Mark other approved library rows with the same PEL ref as superseded.

    This is the only place a library document reaches ``SUPERSEDED``, so it is
    also where a supersede-anchored retention clock starts (CUT-1 / R19).
    """
    if not pel_doc_ref:
        return []
    superseded_at = superseded_at or datetime.now(timezone.utc)

    stmt = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.pel_doc_ref == pel_doc_ref,
        Document.id != current_document_id,
        Document.is_active.is_(True),
        or_(
            Document.status == DocumentStatus.APPROVED,
            Document.status == DocumentStatus.PUBLISHED,
            Document.status == DocumentStatus.ACTIVE,
        ),
    )
    result = await db.execute(stmt)
    superseded_ids: list[int] = []
    for prior in result.scalars().all():
        prior.status = DocumentStatus.SUPERSEDED
        apply_supersede_retention(prior, superseded_at)
        superseded_ids.append(prior.id)
    return superseded_ids
