"""WI-2 / L-32 — occurrence file homes → Register ``documents.id``.

Register ``documents`` is the only library file home (F-3 / F-7). Planet Mark
evidence, case evidence assets and UVDB presented lists are *occurrences* of a
file, and this module holds the only two ways one of them may claim a Register
identity:

1. **Steward** — a human names the Register document id.
2. **Proven content match** — the same content hash, or the identical blob path,
   already exists on the Register in the same tenant.

Nothing here inserts a ``documents`` row. A promote that finds no Register match
returns ``UNMATCHED`` and writes nothing, because creating a Register document as
a side effect of an upload is how a library fills with files nobody filed. The
occurrence keeps its own blob and metadata either way.

Both paths are tenant-scoped on the way in. A link is a readable pointer from one
tenant's record to a ``documents`` row, so accepting an id without checking its
tenant would hand a caller a cross-tenant reference; an id that does not resolve
inside the caller's tenant is reported as ``DOCUMENT_NOT_FOUND`` and not stored.

Filename similarity is deliberately *not* a link path. It is good enough for the
steward-facing dry run (``scripts/governance/library/file_homes_migrate_prep.py``)
where a human reviews every row, and not good enough to write a governance link
from, because two tenants' "Fuel Card July.pdf" are not the same document.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document
from src.domain.models.document_control import ControlledDocument
from src.domain.models.evidence_asset import EvidenceAsset
from src.domain.models.planet_mark import CarbonEvidence

logger = logging.getLogger(__name__)

#: Keys of the ``uvdb_audit_response.documents_presented`` projection.
PRESENTED_DOCUMENT_KEY = "document_id"
PRESENTED_LABEL_KEY = "label"


class LinkMethod(str, enum.Enum):
    """How a Register identity was established. Never inferred from a name."""

    STEWARD = "steward"
    CONTENT_HASH = "content_hash"
    STORAGE_PATH = "storage_path"


class LinkStatus(str, enum.Enum):
    LINKED = "linked"
    ALREADY_LINKED = "already_linked"
    CLEARED = "cleared"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"
    DOCUMENT_NOT_FOUND = "document_not_found"


@dataclass(frozen=True)
class LinkOutcome:
    """Result of a link attempt. ``written`` says whether the row was touched."""

    status: LinkStatus
    document_id: Optional[int] = None
    method: Optional[LinkMethod] = None
    detail: Optional[str] = None

    @property
    def written(self) -> bool:
        return self.status in {LinkStatus.LINKED, LinkStatus.CLEARED}

    @property
    def is_error(self) -> bool:
        """True when the caller asked for something that cannot be honoured."""
        return self.status in {LinkStatus.DOCUMENT_NOT_FOUND, LinkStatus.AMBIGUOUS}


# ---------------------------------------------------------------------------
# Register lookups (read-only — this module never inserts into documents)
# ---------------------------------------------------------------------------


async def register_document_exists(db: AsyncSession, *, tenant_id: Optional[int], document_id: int) -> bool:
    """True when ``document_id`` is a Register document in this tenant."""
    if tenant_id is None:
        return False
    found = await db.scalar(
        select(Document.id).where(Document.id == document_id, Document.tenant_id == tenant_id).limit(1)
    )
    return found is not None


async def _match_by_content_hash(db: AsyncSession, *, tenant_id: int, content_hash: str) -> LinkOutcome:
    """Resolve a Register id from a content hash, via the control layer.

    The Register itself stores no checksum — ``documents`` / ``document_versions``
    carry a path and a size, not a digest — so the only hash the platform holds
    for a filed document is ``controlled_documents.checksum`` on a control record
    that is already anchored to a Register row by ``library_document_id`` (DS-5).
    Reading the hash through that anchor keeps this an existing-fact match rather
    than a new column, at the cost of only covering documents that are under
    control. Uncovered documents fall through to the path match and then to the
    steward queue, which is the honest outcome, not a guess.

    The join to ``documents`` is what makes the result tenant-safe. Filtering the
    control record's tenant alone would trust ``library_document_id`` to point
    inside that tenant; the FK does not promise that, and this must not be the
    code that discovers it doesn't.
    """
    digest = content_hash.strip().lower()
    if not digest:
        # A blank digest is not evidence of anything, and comparing it would match
        # every control record whose checksum was never computed.
        return LinkOutcome(LinkStatus.UNMATCHED)
    rows = await db.execute(
        select(Document.id)
        .join(ControlledDocument, ControlledDocument.library_document_id == Document.id)
        .where(
            Document.tenant_id == tenant_id,
            ControlledDocument.tenant_id == tenant_id,
            func.lower(ControlledDocument.checksum) == digest,
        )
        .distinct()
        .limit(2)
    )
    candidates = [int(value) for (value,) in rows.all() if value is not None]
    if not candidates:
        return LinkOutcome(LinkStatus.UNMATCHED)
    if len(candidates) > 1:
        return LinkOutcome(
            LinkStatus.AMBIGUOUS,
            detail=f"{len(candidates)} Register documents share this content hash",
        )
    return LinkOutcome(LinkStatus.LINKED, document_id=candidates[0], method=LinkMethod.CONTENT_HASH)


async def _match_by_storage_path(db: AsyncSession, *, tenant_id: int, paths: Iterable[Optional[str]]) -> LinkOutcome:
    """Resolve a Register id from an identical blob path in the same tenant."""
    wanted = sorted({path.strip() for path in paths if path and path.strip()})
    if not wanted:
        return LinkOutcome(LinkStatus.UNMATCHED)
    rows = await db.execute(
        select(Document.id).where(Document.tenant_id == tenant_id, Document.file_path.in_(wanted)).distinct().limit(2)
    )
    candidates = [int(value) for (value,) in rows.all()]
    if not candidates:
        return LinkOutcome(LinkStatus.UNMATCHED)
    if len(candidates) > 1:
        return LinkOutcome(
            LinkStatus.AMBIGUOUS,
            detail=f"{len(candidates)} Register documents share this blob path",
        )
    return LinkOutcome(LinkStatus.LINKED, document_id=candidates[0], method=LinkMethod.STORAGE_PATH)


async def match_register_document(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    content_hash: Optional[str] = None,
    paths: Sequence[Optional[str]] = (),
) -> LinkOutcome:
    """Find the Register document this occurrence already *is*, or report why not.

    Order is strongest-evidence-first: identical content, then identical blob
    path. Both must resolve to exactly one document; two candidates is reported
    as ``AMBIGUOUS`` rather than resolved by picking one, because picking one is
    indistinguishable from guessing to everybody downstream.
    """
    if tenant_id is None:
        return LinkOutcome(LinkStatus.UNMATCHED, detail="no tenant scope — nothing may be matched")
    if content_hash:
        outcome = await _match_by_content_hash(db, tenant_id=tenant_id, content_hash=content_hash)
        if outcome.status is not LinkStatus.UNMATCHED:
            return outcome
    return await _match_by_storage_path(db, tenant_id=tenant_id, paths=paths)


# ---------------------------------------------------------------------------
# Planet Mark evidence (carbon_evidence)
# ---------------------------------------------------------------------------


async def link_carbon_evidence(
    db: AsyncSession,
    evidence: CarbonEvidence,
    *,
    tenant_id: Optional[int],
    document_id: Optional[int],
) -> LinkOutcome:
    """Steward path: file this Planet Mark evidence under a named Register document.

    ``document_id=None`` clears the link, which a steward needs when the wrong
    document was named. Clearing removes the claim only; the Planet Mark row, its
    blob and its verification metadata are untouched.
    """
    if document_id is None:
        if evidence.document_id is None:
            return LinkOutcome(LinkStatus.UNMATCHED, detail="no link to clear")
        previous = evidence.document_id
        evidence.document_id = None
        return LinkOutcome(LinkStatus.CLEARED, document_id=previous, method=LinkMethod.STEWARD)
    if evidence.document_id == document_id:
        return LinkOutcome(LinkStatus.ALREADY_LINKED, document_id=document_id, method=LinkMethod.STEWARD)
    if not await register_document_exists(db, tenant_id=tenant_id, document_id=document_id):
        return LinkOutcome(
            LinkStatus.DOCUMENT_NOT_FOUND,
            document_id=document_id,
            detail="no Register document with that id in this tenant",
        )
    evidence.document_id = document_id
    return LinkOutcome(LinkStatus.LINKED, document_id=document_id, method=LinkMethod.STEWARD)


async def promote_carbon_evidence(
    db: AsyncSession,
    evidence: CarbonEvidence,
    *,
    tenant_id: Optional[int],
) -> LinkOutcome:
    """Match path: link only when the Register already holds this exact file."""
    if evidence.document_id is not None:
        return LinkOutcome(LinkStatus.ALREADY_LINKED, document_id=evidence.document_id)
    outcome = await match_register_document(
        db,
        tenant_id=tenant_id,
        content_hash=evidence.file_hash,
        paths=(evidence.storage_key, evidence.file_path),
    )
    if outcome.status is LinkStatus.LINKED and outcome.document_id is not None:
        evidence.document_id = outcome.document_id
        logger.info(
            "carbon_evidence id=%s linked to documents id=%s by %s",
            evidence.id,
            outcome.document_id,
            outcome.method.value if outcome.method else "unknown",
        )
    return outcome


# ---------------------------------------------------------------------------
# Case evidence assets (evidence_assets)
# ---------------------------------------------------------------------------


async def link_evidence_asset(
    db: AsyncSession,
    asset: EvidenceAsset,
    *,
    tenant_id: Optional[int],
    document_id: Optional[int],
) -> LinkOutcome:
    """Steward path: record that this case asset has been filed to the Library.

    The case store stays the read path for the investigation. This only records
    that the same file is on the Register, so a later F-3 cut can retire the
    duplicate rather than having to reconstruct which asset was which document.
    """
    if document_id is None:
        if asset.document_id is None:
            return LinkOutcome(LinkStatus.UNMATCHED, detail="no link to clear")
        previous = asset.document_id
        asset.document_id = None
        return LinkOutcome(LinkStatus.CLEARED, document_id=previous, method=LinkMethod.STEWARD)
    if asset.document_id == document_id:
        return LinkOutcome(LinkStatus.ALREADY_LINKED, document_id=document_id, method=LinkMethod.STEWARD)
    if not await register_document_exists(db, tenant_id=tenant_id, document_id=document_id):
        return LinkOutcome(
            LinkStatus.DOCUMENT_NOT_FOUND,
            document_id=document_id,
            detail="no Register document with that id in this tenant",
        )
    asset.document_id = document_id
    return LinkOutcome(LinkStatus.LINKED, document_id=document_id, method=LinkMethod.STEWARD)


async def promote_evidence_asset(
    db: AsyncSession,
    asset: EvidenceAsset,
    *,
    tenant_id: Optional[int],
) -> LinkOutcome:
    """Match path for a case asset. Unmatched assets legitimately stay case-scoped."""
    if asset.document_id is not None:
        return LinkOutcome(LinkStatus.ALREADY_LINKED, document_id=asset.document_id)
    outcome = await match_register_document(
        db,
        tenant_id=tenant_id,
        content_hash=asset.checksum_sha256,
        paths=(asset.storage_key,),
    )
    if outcome.status is LinkStatus.LINKED and outcome.document_id is not None:
        asset.document_id = outcome.document_id
        logger.info(
            "evidence_assets id=%s linked to documents id=%s by %s",
            asset.id,
            outcome.document_id,
            outcome.method.value if outcome.method else "unknown",
        )
    return outcome


# ---------------------------------------------------------------------------
# UVDB documents_presented projection
# ---------------------------------------------------------------------------


def presented_element_parts(element: Any) -> tuple[Optional[int], Optional[str]]:
    """Split one legacy ``documents_presented`` element into (id claim, label).

    Handles every shape the audit responses have carried: a free-text title, a
    bare Register id, a numeric string, and a dict keyed on any of
    ``document_id`` / ``id`` / ``label`` / ``title`` / ``name``. The id is a
    *claim* at this point — it is verified against the tenant before it reaches
    the projection.
    """
    if element is None:
        return None, None
    if isinstance(element, Mapping):
        raw_id = element.get(PRESENTED_DOCUMENT_KEY, element.get("id"))
        label = element.get(PRESENTED_LABEL_KEY) or element.get("title") or element.get("name")
        return _as_document_id(raw_id), _as_label(label)
    if isinstance(element, bool):
        # A bool is not an id and not a title; keep it visible as a label.
        return None, _as_label(element)
    if isinstance(element, int):
        return element if element > 0 else None, None
    text = str(element).strip()
    if not text:
        return None, None
    if text.isdigit():
        return _as_document_id(text), text
    return None, text


def _as_document_id(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    if text.isdigit():
        number = int(text)
        return number if number > 0 else None
    return None


def _as_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def presented_projection(document_id: Optional[int], label: Optional[str]) -> dict[str, Any]:
    return {PRESENTED_DOCUMENT_KEY: document_id, PRESENTED_LABEL_KEY: label}


async def normalise_documents_presented(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    elements: Any,
) -> Any:
    """Project a presented list onto ``{document_id, label}`` elements.

    Every element keeps its human label whatever happens, and an element only
    carries a ``document_id`` when that id resolves to a Register document in
    this tenant. An unresolvable title stays ``{"document_id": null, "label":
    "<original>"}`` — a steward files it and re-presents it. Nothing here creates
    a Register document, so a UVDB answer can never conjure a filed document.

    Non-list values are returned untouched: the write schema already constrains
    this field to a list, and silently rewriting an unexpected legacy shape would
    destroy the only copy of it.
    """
    if elements is None or not isinstance(elements, list):
        return elements
    if not elements:
        return []

    parts = [presented_element_parts(element) for element in elements]
    claimed_ids = {document_id for document_id, _ in parts if document_id is not None}
    labels_needing_lookup = {label.lower() for document_id, label in parts if document_id is None and label is not None}

    verified_ids = await _verify_document_ids(db, tenant_id=tenant_id, document_ids=claimed_ids)
    resolved_labels = await _resolve_labels(db, tenant_id=tenant_id, labels=labels_needing_lookup)

    projection: list[dict[str, Any]] = []
    for document_id, label in parts:
        if document_id is not None:
            if document_id in verified_ids:
                projection.append(presented_projection(document_id, label))
            else:
                # Keep the claim visible as a label rather than storing an id
                # this tenant cannot see.
                projection.append(presented_projection(None, label or str(document_id)))
            continue
        resolved = resolved_labels.get(label.lower()) if label else None
        projection.append(presented_projection(resolved, label))
    return projection


async def _verify_document_ids(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    document_ids: set[int],
) -> set[int]:
    if tenant_id is None or not document_ids:
        return set()
    rows = await db.execute(
        select(Document.id).where(Document.tenant_id == tenant_id, Document.id.in_(sorted(document_ids)))
    )
    return {int(value) for (value,) in rows.all()}


async def _resolve_labels(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    labels: set[str],
) -> dict[str, int]:
    """Map lowercased label → Register id, only where exactly one row matches.

    Title and file name are both accepted because auditors type whichever they
    were shown. An ambiguous label resolves to nothing: two documents with the
    same title in one tenant is precisely the case where a machine choice would
    file the wrong evidence.
    """
    if tenant_id is None or not labels:
        return {}
    rows = await db.execute(
        select(Document.id, Document.file_name, Document.title).where(
            Document.tenant_id == tenant_id,
            or_(
                func.lower(Document.file_name).in_(sorted(labels)),
                func.lower(Document.title).in_(sorted(labels)),
            ),
        )
    )
    candidates: dict[str, set[int]] = {}
    for document_id, file_name, title in rows.all():
        for value in (file_name, title):
            key = _as_label(value)
            if key is None:
                continue
            key = key.lower()
            if key in labels:
                candidates.setdefault(key, set()).add(int(document_id))
    return {label: next(iter(ids)) for label, ids in candidates.items() if len(ids) == 1}
