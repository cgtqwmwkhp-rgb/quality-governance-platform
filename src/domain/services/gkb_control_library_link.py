"""Controlled document ↔ library document golden-thread linking.

DS-5: hard FK on ``controlled_documents.library_document_id`` with safe soft-match
backfill when exactly one same-tenant title/reference candidate exists.

WC-1 / L-01d converges the two registers onto this one anchor rather than adding
a third home: control state is projected onto the Register row it is anchored to,
and a library approve/publish is written through to that control record so the
two cannot report different lifecycle states for the same document.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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
            select(func.count()).select_from(ControlledDocument).where(ControlledDocument.library_document_id.is_(None))
        )
        or 0
    )


# ---------------------------------------------------------------------------
# WC-1 / L-01d — one Register, control state folded onto it
# ---------------------------------------------------------------------------

#: Library statuses that mean "this version is the controlled one", mapped to the
#: controlled-document vocabulary. Only these two transitions are written
#: through: they are the ones a control record is expected to agree with, and a
#: draft/under-review library row says nothing about control state that the
#: control record does not already say better.
_LIBRARY_TO_CONTROL_STATUS = {
    "approved": "approved",
    "published": "published",
}


def _naive_utcnow() -> datetime:
    """Now, as the naive value ``controlled_documents`` DateTime columns hold.

    Those columns are declared without ``timezone=True``, and asyncpg refuses an
    aware datetime for them — see the same note in ``routes/document_control.py``.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def controlled_for_library_document(
    db: AsyncSession,
    *,
    tenant_id: int,
    library_document_id: int,
) -> ControlledDocument | None:
    """The control record anchored to a Register document, if one exists."""
    return await db.scalar(
        select(ControlledDocument)
        .where(
            ControlledDocument.tenant_id == tenant_id,
            ControlledDocument.library_document_id == library_document_id,
        )
        .order_by(ControlledDocument.id.asc())
        .limit(1)
    )


async def control_state_for_documents(
    db: AsyncSession,
    *,
    tenant_id: int,
    document_ids: list[int],
) -> dict[int, tuple[int, str]]:
    """Map Register document id → (controlled document id, control status).

    One query for the whole page. The Register list already batch-loads its other
    joins to stay off the N+1 path and control state has to follow the same rule;
    a per-row lookup here would put a query per document on the busiest list in
    the product.

    Where two control records share an anchor — possible on deployments that ran
    the ``20260724`` soft-match backfill — the lowest id wins, deterministically,
    so the Register does not alternate between them between reads.
    """
    if not document_ids:
        return {}

    rows = await db.execute(
        select(
            ControlledDocument.library_document_id,
            ControlledDocument.id,
            ControlledDocument.status,
        )
        .where(
            ControlledDocument.tenant_id == tenant_id,
            ControlledDocument.library_document_id.in_(document_ids),
        )
        .order_by(ControlledDocument.id.asc())
    )
    state: dict[int, tuple[int, str]] = {}
    for library_document_id, controlled_id, status in rows.all():
        if library_document_id is None or library_document_id in state:
            continue
        state[library_document_id] = (controlled_id, str(status or ""))
    return state


async def write_library_decision_through_to_control(
    db: AsyncSession,
    document: LibraryDocument,
    *,
    library_status: str,
    version_number: str | None,
    actor_id: int | None,
    actor_name: str | None,
) -> ControlledDocument | None:
    """Propagate a library approve/publish onto the anchored control record.

    Before WC-1 a document could be approved and published on the Register while
    its control record still read ``draft``, because the library lifecycle never
    touched it — two registers, two answers, and the Document Control page was
    the one an auditor would be shown. This writes the decision through inside
    the caller's transaction, so either both records move or neither does.

    Deliberately does not *create* a control record: bringing a document under
    control is a human filing decision (L-18c / WD-1), and inventing a control
    record as a side effect of publishing would be exactly the silent governance
    write the product locks forbid. Returns ``None`` when there is nothing
    anchored, which is a document that is simply not under control.

    ``approver_id`` / ``approver_name`` / ``approved_date`` are written only by an
    approval. A publish moves ``status`` and ``effective_date`` and leaves the
    approval attribution alone: naming the publisher as approver would make the
    control record assert an approval that never happened, and would overwrite the
    real approver's name when a document goes through approve *then* publish.
    """
    mapped_status = _LIBRARY_TO_CONTROL_STATUS.get(library_status.lower())
    if mapped_status is None:
        return None

    controlled = await controlled_for_library_document(
        db,
        tenant_id=document.tenant_id,
        library_document_id=document.id,
    )
    if controlled is None:
        return None

    from src.domain.services.document_version_service import parse_version

    now = _naive_utcnow()
    controlled.status = mapped_status
    if mapped_status == "approved":
        controlled.approver_id = actor_id
        controlled.approver_name = actor_name
        controlled.approved_date = now
    else:
        controlled.effective_date = now
    if version_number:
        parsed = parse_version(version_number)
        controlled.current_version = parsed.label
        controlled.major_version = parsed.major
        controlled.minor_version = parsed.minor
    controlled.updated_at = now
    await db.flush()
    return controlled
