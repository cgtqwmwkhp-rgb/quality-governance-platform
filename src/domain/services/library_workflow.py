"""Northern Star Wave W6 / NS-WF — the issue state machine and its issue-time blocks.

W4 (`library_rules.py`) hard-blocks the *identity* rules on create. This module is
the other half staged there: the rules the pack enforces "On issue", plus the
transition table itself, so an illegal status move is refused by one named table
rather than by whichever ad-hoc `if` a call site happened to grow.

The transition table is read from `northern-star-rules-v6.json`
(`workflow_transitions`) — never re-typed here — and projected onto the platform's
`DocumentStatus` enum:

| Northern Star | DocumentStatus |
| ------------- | -------------- |
| Draft         | `DRAFT` (also `INDEXED` / `REJECTED`, see `_STATUS_ALIASES`) |
| In review     | `UNDER_REVIEW` |
| Approved      | `APPROVED` |
| Issued        | `PUBLISHED` |
| Superseded    | `SUPERSEDED` |
| Withdrawn     | `RETIRED` |

Two pack rows are deliberately *not* transitions: "Level change" and "Emergency
reissue" name procedures (withdraw-and-reissue, expedited approval), not target
states. They are surfaced by :data:`PROCEDURAL_ROUTES` so the projection is
auditable against the pack rather than silently lossy, and R05 stays where it is
already enforced — the cascade-level ORM listener in `models/document.py`.

Rules enforced here: R07, R10, R11, R20, R22, R23. R12 (amendment rows immutable)
is already enforced by `DocumentVersion.is_immutable` + `assert_version_mutable`;
R18 (supersede same day) is a same-transaction consequence of the issue transition
and lives in `document_library_lifecycle_service.issue_document`.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import StateTransitionError, ValidationError
from src.domain.models.enums import DocumentStatus

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO_ROOT / "specs" / "governance-library" / "northern-star-rules-v6.json"

# Wave W6 set — the pack's "On issue" blocks plus the transition table.
RULE_WF_IDS: Final[frozenset[str]] = frozenset({"R07", "R10", "R11", "R12", "R14", "R18", "R20", "R22", "R23"})

# Northern Star state name -> platform status. One-way on purpose: several
# platform statuses collapse onto "Draft" (below) and the reverse map would have
# to pick one.
_NS_TO_STATUS: Final[dict[str, DocumentStatus]] = {
    "draft": DocumentStatus.DRAFT,
    "in review": DocumentStatus.UNDER_REVIEW,
    "approved": DocumentStatus.APPROVED,
    "issued": DocumentStatus.PUBLISHED,
    "superseded": DocumentStatus.SUPERSEDED,
    "withdrawn": DocumentStatus.RETIRED,
}

# Platform statuses that *are* the Northern Star "Draft" state for transition
# purposes. `INDEXED` is an ingested file nobody has moved yet and `REJECTED` is a
# draft a reviewer sent back; both were already accepted by `submit_for_review`
# before this table existed, and neither is a distinct Northern Star state. This
# map exists so that fact is written down once instead of being re-derived per
# call site. `UNDER_REVISION` is deliberately absent — it was not submittable
# before and widening it is not this wave's decision to make.
_STATUS_ALIASES: Final[dict[DocumentStatus, DocumentStatus]] = {
    DocumentStatus.INDEXED: DocumentStatus.DRAFT,
    DocumentStatus.REJECTED: DocumentStatus.DRAFT,
}

# Pack rows whose `to` names a procedure rather than a state.
PROCEDURAL_ROUTES: Final[frozenset[str]] = frozenset({"level change", "emergency reissue", "issued (typo correction)"})


@lru_cache(maxsize=1)
def _rules_pack() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def rule_text(rule_id: str) -> str:
    for row in _rules_pack()["validation_rules"]:
        if row["id"] == rule_id:
            return str(row["rule"])
    raise KeyError(rule_id)


@lru_cache(maxsize=1)
def transition_table() -> frozenset[tuple[DocumentStatus, DocumentStatus]]:
    """The legal (from, to) pairs, projected from the pack's `workflow_transitions`.

    A pack row is dropped only when its `from` or `to` is not a Northern Star
    state — i.e. the `PROCEDURAL_ROUTES` and the `from: "Any"` level-change row.
    Anything else that fails to map is a projection defect and raises, so a pack
    edit that renames a state fails loudly at import instead of quietly making an
    illegal move legal.
    """
    pairs: set[tuple[DocumentStatus, DocumentStatus]] = set()
    for row in _rules_pack()["workflow_transitions"]:
        source = str(row["from"]).strip().lower()
        target = str(row["to"]).strip().lower()
        if target in PROCEDURAL_ROUTES or source == "any":
            continue
        try:
            pairs.add((_NS_TO_STATUS[source], _NS_TO_STATUS[target]))
        except KeyError as exc:  # pragma: no cover - guards a pack edit, not a code path
            raise RuntimeError(
                f"northern-star-rules-v6.json workflow_transitions row {row!r} names a state "
                "this projection does not know; update _NS_TO_STATUS or PROCEDURAL_ROUTES"
            ) from exc
    return frozenset(pairs)


def canonical_status(status: DocumentStatus | str | None) -> DocumentStatus | None:
    """Platform status -> the status the transition table is keyed on."""
    if status is None:
        return None
    if isinstance(status, DocumentStatus):
        resolved = status
    else:
        try:
            resolved = DocumentStatus(str(getattr(status, "value", status)).lower())
        except ValueError:
            return None
    return _STATUS_ALIASES.get(resolved, resolved)


def transition_is_allowed(from_status: DocumentStatus | str | None, to_status: DocumentStatus) -> bool:
    source = canonical_status(from_status)
    if source is None:
        return False
    return (source, canonical_status(to_status)) in transition_table()


def assert_transition_allowed(
    from_status: DocumentStatus | str | None,
    to_status: DocumentStatus,
    *,
    document_id: int | None = None,
) -> None:
    """Refuse any status move the Northern Star table does not carry."""
    if transition_is_allowed(from_status, to_status):
        return
    raw = getattr(from_status, "value", from_status)
    raise StateTransitionError(
        f"NS-WF: '{raw}' -> '{to_status.value}' is not a Northern Star workflow transition",
        details={"from": raw, "to": to_status.value, "document_id": document_id},
    )


# ---------------------------------------------------------------------------
# Issue-time blocks
# ---------------------------------------------------------------------------

_WHOLE_VERSION = re.compile(r"^\s*(\d+)(?:\.0+)?\s*$")


def assert_whole_number_version(version_number: str | None, *, rule_id: str = "R22") -> None:
    """R22 — an approved issue carries a whole number; decimals are drafts.

    The platform writes versions as ``major.minor``, so "whole number" is read as
    a zero minor: ``2`` and ``2.0`` are issues, ``2.1`` is a draft. This refuses
    rather than promoting ``2.1`` to ``3`` on the caller's behalf — an issued
    version number is printed on the document face, and inventing one is exactly
    the silent write the product forbids.
    """
    match = _WHOLE_VERSION.fullmatch(version_number or "")
    if match is None or int(match.group(1)) < 1:
        raise ValidationError(
            f"{rule_id}: version {version_number!r} is not an issued version number. "
            "Approved issues are whole numbers from 1 (2 or 2.0); decimals are drafts — "
            "revise to a major version before issuing.",
            details={"rule": rule_id, "version_number": version_number},
        )


def assert_approver_is_not_version_author(*, approver_id: int | None, version_author_id: int | None) -> None:
    """R23 — the approver of a version must not be the author of *that version*.

    The pre-existing self-approval check in ``approve_document`` compares the
    approver against ``document.created_by_id`` (whoever filed the document),
    which still lets the author of revision 3 approve their own revision when
    somebody else filed the document years ago. This closes the leg the pack
    actually names and is applied in addition to, not instead of, that check.

    An unattributed approver or unattributed version is not refused: there is no
    identity to compare, and refusing would block every pre-attribution legacy
    row rather than enforcing a separation of duties.
    """
    if approver_id is None or version_author_id is None:
        return
    if version_author_id == approver_id:
        raise ValidationError(
            "R23: the approver of a version must not be its author. A second person must approve this version.",
            code="SEPARATION_OF_DUTIES",
            details={"rule": "R23", "approver_id": approver_id},
        )


def assert_amendment_record_complete(
    *,
    change_notes: str | None,
    version_number: str | None,
    document_version: str | None,
) -> None:
    """R10 + R11 — an issue needs a completed amendment row that reconciles.

    ``DocumentVersion`` *is* the amendment row: it carries the version number, the
    change note, the date (``created_at``) and the author (``created_by_id``).
    R10 is therefore "the row has a change note"; R11 is "the row being issued is
    the version the document claims". The date/author leg of R11 is not checked —
    there is no modelled control block on the document face to reconcile against
    yet; see the Change Ledger.
    """
    if not (change_notes or "").strip():
        raise ValidationError(
            "R10: no document is issued without a completed amendment record. "
            "Record the change notes on this version before issuing.",
            details={"rule": "R10", "version_number": version_number},
        )
    if (document_version or "").strip() != (version_number or "").strip():
        raise ValidationError(
            f"R11: the amendment row ({version_number!r}) does not match the document "
            f"version ({document_version!r}); approve the version you intend to issue.",
            details={"rule": "R11", "version_number": version_number, "document_version": document_version},
        )


def assert_review_cycle_declared(*, review_cycle_months: int | None, review_cycle_basis: str | None) -> None:
    """R20 — every document states its review cycle *and* the basis for it.

    There is no default cycle by design: the pack says a cycle is justified by
    risk, statute or certification expectation, so a missing basis is refused
    rather than filled in with a house standard nobody agreed to.
    """
    missing = []
    if review_cycle_months is None or int(review_cycle_months) <= 0:
        missing.append("review_cycle_months")
    if not (review_cycle_basis or "").strip():
        missing.append("review_cycle_basis")
    if missing:
        raise ValidationError(
            "R20: a document states its review cycle and the basis for it before issue "
            f"(missing: {', '.join(missing)}). There is no default cycle — justify it by risk, "
            "statute or certification expectation.",
            details={"rule": "R20", "missing": missing},
        )


def assert_parent_named(*, cascade_level: int | None, has_primary_parent: bool) -> None:
    """R07 — every document below L1 names a parent."""
    if cascade_level is None or int(cascade_level) <= 1:
        return
    if not has_primary_parent:
        raise ValidationError(
            f"R07: a level {int(cascade_level)} document names a parent before issue. "
            "Add a confirmed primary Implements edge to its parent document.",
            details={"rule": "R07", "cascade_level": int(cascade_level)},
        )


async def has_confirmed_primary_parent(db: AsyncSession, document: object) -> bool:
    """True when a live, confirmed primary Implements edge points this document at a parent.

    Confirmed only: a `proposed` edge is a suggestion awaiting a human, and R07 is
    a Block rule. Letting an AI proposal satisfy it would make the machine decide
    a document's place in the cascade, which the product forbids.
    """
    from src.domain.models.document_graph import DocumentEdge, DocumentEdgeStatus, DocumentEdgeType

    document_id = getattr(document, "id", None)
    tenant_id = getattr(document, "tenant_id", None)
    if document_id is None or tenant_id is None:
        return False
    found = await db.scalar(
        select(DocumentEdge.id)
        .where(
            DocumentEdge.tenant_id == tenant_id,
            DocumentEdge.src_document_id == document_id,
            DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
            DocumentEdge.is_primary_parent.is_(True),
            DocumentEdge.status == DocumentEdgeStatus.CONFIRMED,
            DocumentEdge.deleted_at.is_(None),
        )
        .limit(1)
    )
    return found is not None
