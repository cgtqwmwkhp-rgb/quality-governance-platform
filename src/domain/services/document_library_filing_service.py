"""Governance Library Wave W1 — filing rules, ACL, retention, duplicate detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document import Document
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus

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
_RETENTION_YEARS_RE = re.compile(r"(\d+)\s*years?", re.IGNORECASE)


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
    value = (default_access or "all_staff").strip().lower()
    if value in {"all_staff", "managers", "restricted"}:
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


def compute_retention_until(category: DocumentCategory, approved_at: datetime) -> Optional[datetime]:
    """Best-effort retention_until from category retention_rule pick-list text."""
    rule = (category.retention_rule or "").strip()
    if not rule:
        return None
    if rule.lower() == "current":
        return None

    match = _RETENTION_YEARS_RE.search(rule)
    if not match:
        return None

    years = int(match.group(1))
    if years <= 0:
        return None
    base = approved_at if approved_at.tzinfo else approved_at.replace(tzinfo=timezone.utc)
    return base + timedelta(days=years * 365)


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
) -> list[int]:
    """Mark other approved library rows with the same PEL ref as superseded."""
    if not pel_doc_ref:
        return []

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
        superseded_ids.append(prior.id)
    return superseded_ids
