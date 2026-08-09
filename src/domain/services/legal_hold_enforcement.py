"""Enforcement of ``matter_legal_holds`` against the document lifecycle (WC-1 / L-40).

The hold register itself is unchanged and remains the only source of truth for
whether a matter is held: this module never records, infers or caches hold state.
It answers one question — *is this document frozen right now* — and refuses the
caller when the answer is yes.

Scope resolution
----------------
A hold is issued against a ``matter_reference``, and ``documents``
.``legal_matter_reference`` records which matter a Register document is filed
under. A document is frozen while an ACTIVE hold exists for that matter *in the
same tenant*. A document filed under no matter is not frozen — that is a
positive fact about the filing, not a missing reading.

Fail closed
-----------
The check runs before any mutation is staged and nothing here swallows database
errors: if hold state cannot be read, the exception propagates and the caller's
transaction never commits. A refusal is therefore the outcome of both "a hold
exists" and "we could not tell", which is the only safe pairing for a control
whose purpose is preventing spoliation.

Two limits are deliberate rather than overlooked:

* One matter per document. A document needed by a second matter is held through
  the matter it is filed under; the column cannot record both. Recording several
  would need a scope table, which is a bigger change than this slice makes.
* Read-committed race. A hold committed by another transaction *after* this
  check passes cannot retroactively refuse the in-flight call. The window is one
  statement wide, and the gates downstream of a revision — approve and publish —
  each re-run this check, so the outcome a hold exists to prevent (a held record
  reaching a new published state) is still refused on the next transition.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ConflictError
from src.domain.models.document import Document
from src.domain.models.legal_hold import LegalHoldStatus, MatterLegalHold

#: Wire-visible code for a refusal caused by an active hold. Deliberately not an
#: ``ErrorCode`` member: like ``MALWARE_SCAN_PENDING`` it is a specific reason
#: inside the generic 409 envelope, not a new class of error.
LEGAL_HOLD_ACTIVE = "LEGAL_HOLD_ACTIVE"


def matter_reference_of(document: object) -> str | None:
    """The matter a document is filed under, normalised, or ``None``.

    Blank and whitespace-only values are treated as "no matter" so a stray empty
    string cannot silently become a hold scope that matches nothing.
    """
    raw = getattr(document, "legal_matter_reference", None)
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    return trimmed or None


async def active_hold_for_matter(
    db: AsyncSession,
    *,
    tenant_id: int,
    matter_reference: str,
) -> MatterLegalHold | None:
    """The active hold on ``matter_reference`` for this tenant, if any."""
    return await db.scalar(
        select(MatterLegalHold)
        .where(
            MatterLegalHold.tenant_id == tenant_id,
            MatterLegalHold.matter_reference == matter_reference,
            MatterLegalHold.status == LegalHoldStatus.ACTIVE,
        )
        .order_by(MatterLegalHold.id.asc())
        .limit(1)
    )


async def active_hold_for_document(db: AsyncSession, document: Document) -> MatterLegalHold | None:
    """The active hold freezing ``document``, or ``None`` when it is not held."""
    matter = matter_reference_of(document)
    if matter is None:
        return None
    tenant_id = getattr(document, "tenant_id", None)
    if tenant_id is None:
        # A document row always carries a tenant; an object that does not is a
        # caller defect, and guessing a tenant here would read another one's holds.
        raise ConflictError(
            "Legal-hold state cannot be established without a tenant.",
            code=LEGAL_HOLD_ACTIVE,
            details={"matter_reference": matter},
        )
    return await active_hold_for_matter(db, tenant_id=tenant_id, matter_reference=matter)


async def assert_document_not_held(db: AsyncSession, document: Document, *, action: str) -> None:
    """Refuse ``action`` while an active legal hold freezes ``document``."""
    hold = await active_hold_for_document(db, document)
    if hold is None:
        return
    raise ConflictError(
        f"Document is under legal hold for matter '{hold.matter_reference}' and cannot be {action}. "
        "Release the hold before changing this record.",
        code=LEGAL_HOLD_ACTIVE,
        details={
            "action": action,
            "matter_reference": hold.matter_reference,
            "legal_hold_id": hold.id,
            "document_id": getattr(document, "id", None),
        },
    )


async def assert_controlled_document_not_held(
    db: AsyncSession,
    controlled: object,
    *,
    tenant_id: int,
    action: str,
) -> None:
    """Refuse ``action`` on a controlled document whose Register row is held.

    Hold scope lives on the Register row (D1), so a controlled record is frozen
    through its ``library_document_id`` anchor. An unanchored control record has
    no Register row to carry a matter and therefore cannot be in scope of a
    document-level hold — WC-1 stops new ones being created unanchored, and the
    ones that predate it are reported by ``count_unlinked_controlled``.
    """
    library_document_id = getattr(controlled, "library_document_id", None)
    if library_document_id is None:
        return
    document = await db.scalar(
        select(Document).where(
            Document.id == library_document_id,
            Document.tenant_id == tenant_id,
        )
    )
    if document is None:
        return
    await assert_document_not_held(db, document, action=action)


async def held_document_ids(
    db: AsyncSession,
    *,
    tenant_id: int,
    documents: Sequence[Document],
) -> set[int]:
    """Which of ``documents`` are frozen, in one query rather than one each.

    Used by the Register projection: the list already batch-loads its joins to
    stay off the N+1 path, and hold state has to follow the same rule.
    """
    matters = {matter for matter in (matter_reference_of(d) for d in documents) if matter is not None}
    if not matters:
        return set()

    rows = await db.execute(
        select(MatterLegalHold.matter_reference).where(
            MatterLegalHold.tenant_id == tenant_id,
            MatterLegalHold.matter_reference.in_(matters),
            MatterLegalHold.status == LegalHoldStatus.ACTIVE,
        )
    )
    held_matters = {row[0] for row in rows.all()}
    if not held_matters:
        return set()
    return {d.id for d in documents if (matter := matter_reference_of(d)) is not None and matter in held_matters}


def not_under_active_legal_hold():
    """SQL predicate excluding held documents from a ``documents`` query.

    Returned as a predicate rather than applied to a session so disposal can put
    it inside the same statement that selects candidates. A held document is then
    never a member of the eligible set, which cannot be bypassed by a caller that
    forgets to run a separate check.
    """
    return ~exists(
        select(MatterLegalHold.id).where(
            MatterLegalHold.tenant_id == Document.tenant_id,
            MatterLegalHold.status == LegalHoldStatus.ACTIVE,
            Document.legal_matter_reference.is_not(None),
            MatterLegalHold.matter_reference == Document.legal_matter_reference,
        )
    )
