"""Controlled document ↔ library document golden-thread linking.

DS-5: hard FK on ``controlled_documents.library_document_id`` with safe soft-match
backfill when exactly one same-tenant title/reference candidate exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document as LibraryDocument
from src.domain.models.document_control import ControlledDocument


@dataclass(frozen=True)
class SoftLibraryMatch:
    """Outcome of resolving a controlled document to a library row."""

    library_document_id: int | None
    matching_fields: tuple[str, ...]
    relationship_state: str  # linked | unverified_candidate | ambiguous | not_found


def matching_fields_for(controlled: ControlledDocument, library: LibraryDocument) -> list[str]:
    fields: list[str] = []
    if library.title == controlled.title:
        fields.append("title")
    ref = getattr(library, "reference_number", None)
    if ref and ref == controlled.document_number:
        fields.append("reference_number")
    return fields


async def resolve_library_for_controlled(
    db: AsyncSession,
    document: ControlledDocument,
    *,
    tenant_id: int,
) -> tuple[LibraryDocument | None, SoftLibraryMatch]:
    """Return the governed library row when hard-linked, else a soft candidate."""
    if document.library_document_id is not None:
        linked = await db.scalar(
            select(LibraryDocument).where(
                LibraryDocument.id == document.library_document_id,
                LibraryDocument.tenant_id == tenant_id,
            )
        )
        if linked is not None:
            return linked, SoftLibraryMatch(
                library_document_id=linked.id,
                matching_fields=tuple(matching_fields_for(document, linked)),
                relationship_state="linked",
            )

    candidates_result = await db.execute(
        select(LibraryDocument)
        .where(
            LibraryDocument.tenant_id == tenant_id,
            or_(
                LibraryDocument.title == document.title,
                LibraryDocument.reference_number == document.document_number,
            ),
        )
        .order_by(LibraryDocument.id)
        .limit(2)
    )
    candidates = list(candidates_result.scalars().all())
    if not candidates:
        return None, SoftLibraryMatch(None, (), "not_found")
    if len(candidates) > 1:
        return None, SoftLibraryMatch(None, (), "ambiguous")

    candidate = candidates[0]
    return candidate, SoftLibraryMatch(
        library_document_id=None,
        matching_fields=tuple(matching_fields_for(document, candidate)),
        relationship_state="unverified_candidate",
    )


SOFT_MATCH_BACKFILL_SQL = """
UPDATE controlled_documents cd
SET library_document_id = matches.library_id
FROM (
    SELECT cd2.id AS controlled_id, MIN(d.id) AS library_id
    FROM controlled_documents cd2
    JOIN documents d
      ON d.tenant_id = cd2.tenant_id
     AND (
         d.title = cd2.title
         OR d.reference_number = cd2.document_number
     )
    WHERE cd2.library_document_id IS NULL
    GROUP BY cd2.id
    HAVING COUNT(d.id) = 1
) matches
WHERE cd.id = matches.controlled_id
  AND cd.library_document_id IS NULL
"""


async def count_unlinked_controlled(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(ControlledDocument)
            .where(ControlledDocument.library_document_id.is_(None))
        )
        or 0
    )
