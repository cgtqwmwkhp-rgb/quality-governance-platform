"""STEWARD-14 — the accepted retention decisions, and the one place they win.

CUT-1 built the mechanism that turns a taxonomy ``retention_rule`` into
``(years, anchor)`` and, crucially, **refuses** fourteen rules rather than
guessing which of the two periods they name is the real one. That refusal is
honest but it is not an answer: ADR-0023 says Citation (ATLAS) is not retired for
a category until that category has an executable retention, so fourteen refusals
were fourteen open items rather than a finished cutover.

This module carries the answers. ``specs/governance-library/steward_retention_decisions.json``
records, per ``taxonomy_id``, the years and anchor a steward accepted — nothing
else. In particular it does **not** copy the prose:

- ``taxonomy.json`` ``retention_rule`` remains the governance authority and the
  R19 "basis". It is unchanged by STEWARD-14; no period in it was shortened,
  lengthened or reworded to make a decision fit.
- The decision file holds the steward's *reading* of that prose. Two files, two
  different facts, one home each (F-7 §4).

Precedence
----------
``resolve_category_retention`` is the only composition point: a steward decision
for that ``taxonomy_id`` wins, otherwise the prose is read by
``resolve_retention_rule``. It answers the question "what should this category's
``retention_years`` / ``retention_anchor`` columns say", and it has exactly two
callers — the seed projection and the cutover readiness gate — so those two can
never disagree.

Filing is deliberately *not* a caller. Once the seed has run, the decision is on
the ``document_categories`` row, and ``document_library_filing_service`` reads
those stored columns (falling back to the prose). Reading this file at file time
as well would add a third precedence layer to a decision that already has a
system of record.

Why the decision has to live outside the seed derivation
--------------------------------------------------------
Before this module, ``seed_document_categories`` re-derived both columns from the
prose on every run and wrote the result unconditionally. A steward who resolved a
blocker by setting the columns in the database — the workflow CUT-1's own design
note tells them to use — would have had that decision silently overwritten by the
next reseed, redeploy or admin "reload seed" click. The decision therefore has to
be an input to the seed, not something the seed can only destroy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Optional

from src.domain.services.library_retention_policy import (
    RetentionAnchor,
    RetentionDecision,
    RetentionPolicy,
    resolve_retention_rule,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
STEWARD_DECISIONS_JSON_PATH: Final[Path] = (
    _REPO_ROOT / "specs" / "governance-library" / "steward_retention_decisions.json"
)

#: Provenance labels for a category's retention columns. Stable strings — the
#: readiness report groups by them and the PR/compliance narrative quotes them.
SOURCE_STEWARD_DECISION: Final[str] = "steward_decision"
SOURCE_TAXONOMY_PROSE: Final[str] = "taxonomy_prose"

#: Anchors a steward decision may name. ``event`` and ``indefinite`` are
#: excluded on purpose: a decision exists to make a category *computable*, and
#: neither of those ever yields a disposal date, so recording one here would be a
#: decision that changes nothing while reading as though it had.
DECIDABLE_ANCHORS: Final[tuple[str, ...]] = (RetentionAnchor.ISSUE.value, RetentionAnchor.SUPERSEDE.value)


@dataclass(frozen=True)
class StewardRetentionDecision:
    """One accepted decision: the number, the anchor, and why."""

    taxonomy_id: str
    years: int
    anchor: RetentionAnchor
    rationale: str


@dataclass(frozen=True)
class StewardRetentionDecisionSet:
    """The decision file as loaded: the acceptance metadata plus the decisions."""

    accepted_by: str
    accepted_on: str
    decisions: dict[str, StewardRetentionDecision]


def _parse(payload: dict[str, object], *, source: Path) -> StewardRetentionDecisionSet:
    rows = payload.get("decisions")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{source.name} contains no decisions")

    decisions: dict[str, StewardRetentionDecision] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{source.name} contains a non-object decision")
        taxonomy_id = str(row.get("taxonomy_id", "")).strip()
        if not taxonomy_id:
            raise ValueError(f"{source.name} contains a decision with no taxonomy_id")
        if taxonomy_id in decisions:
            # Two answers for one category is not a decision. Silently taking
            # either one would put a period nobody accepted onto a disposal queue.
            raise ValueError(f"{source.name} contains duplicate decisions for taxonomy_id {taxonomy_id!r}")

        years = row.get("retention_years")
        if not isinstance(years, int) or isinstance(years, bool) or years <= 0:
            raise ValueError(f"{source.name}: {taxonomy_id} retention_years must be a positive integer, got {years!r}")

        anchor_value = str(row.get("retention_anchor", "")).strip().lower()
        if anchor_value not in DECIDABLE_ANCHORS:
            raise ValueError(
                f"{source.name}: {taxonomy_id} retention_anchor must be one of "
                f"{DECIDABLE_ANCHORS}, got {row.get('retention_anchor')!r}"
            )

        rationale = str(row.get("rationale", "")).strip()
        if not rationale:
            # R19 wants a basis. The prose is the basis for the period; the
            # rationale is the basis for *choosing this reading of it*, and a
            # decision no one can explain is not auditable.
            raise ValueError(f"{source.name}: {taxonomy_id} has no rationale")

        decisions[taxonomy_id] = StewardRetentionDecision(
            taxonomy_id=taxonomy_id,
            years=years,
            anchor=RetentionAnchor(anchor_value),
            rationale=rationale,
        )

    accepted_by = str(payload.get("accepted_by", "")).strip()
    accepted_on = str(payload.get("accepted_on", "")).strip()
    if not accepted_by or not accepted_on:
        raise ValueError(f"{source.name} must record accepted_by and accepted_on")

    return StewardRetentionDecisionSet(accepted_by=accepted_by, accepted_on=accepted_on, decisions=decisions)


def load_steward_retention_decisions(path: Path | None = None) -> StewardRetentionDecisionSet:
    """Parse and validate the decision file. Raises rather than degrading.

    A malformed decision file is refused outright instead of contributing the
    rows it can read. Half a decision set would leave some categories on the
    prose derivation and some on a steward decision with no way to tell which,
    and the seed would then write that mixture to the database.
    """
    source = path or STEWARD_DECISIONS_JSON_PATH
    return _parse(json.loads(source.read_text(encoding="utf-8")), source=source)


@lru_cache(maxsize=1)
def _default_decision_set() -> StewardRetentionDecisionSet:
    return load_steward_retention_decisions()


def steward_retention_decisions() -> dict[str, StewardRetentionDecision]:
    """The accepted decisions, keyed by ``taxonomy_id`` (read-only snapshot)."""
    return dict(_default_decision_set().decisions)


def steward_decision_for(taxonomy_id: Optional[str]) -> Optional[StewardRetentionDecision]:
    """The accepted decision for one category, or ``None`` if it has none."""
    if not taxonomy_id:
        return None
    return _default_decision_set().decisions.get(taxonomy_id.strip())


def resolve_category_retention(
    taxonomy_id: Optional[str],
    retention_rule: Optional[str],
) -> RetentionDecision:
    """What this category's retention columns should say: steward first, then prose.

    The returned policy's ``basis`` is the taxonomy prose either way. R19's basis
    is the governance text, and a steward decision is a reading of that text, not
    a replacement for it — so a document filed under a steward-decided category
    still carries the rule it was actually filed under. Provenance is not lost:
    ``steward_decision_for`` answers "was this decided or derived", keyed by the
    same ``taxonomy_id``.
    """
    decision = steward_decision_for(taxonomy_id)
    if decision is None:
        return resolve_retention_rule(retention_rule)
    basis = " ".join((retention_rule or "").split())
    return RetentionDecision(
        RetentionPolicy(decision.years, decision.anchor, basis),
        decision.anchor.value,
    )
