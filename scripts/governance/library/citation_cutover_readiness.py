#!/usr/bin/env python3
"""CUT-1 — is QGP actually ready to be the system of record? (read-only)

ADR-0023 decides that "QGP becomes the system of record. Citation (ATLAS) ceases
to be authoritative for these documents." Its own risk register attaches a
condition to that sentence:

    Nothing can calculate a disposal date, so the 7-year Citation position is not
    in fact being replaced by anything executable. Mitigation: treat
    machine-readable retention (``retention_years`` + ``retention_basis``) as a
    prerequisite of cutover, not a follow-up.

F-7 §2 restates it as a gate: "Citation SoR retirement requires executable
retention on library documents — free-text ``retention_rule`` alone is
insufficient."

This script is that gate, made answerable. It classifies every checked-in
taxonomy category and reports which categories can produce a disposal date,
which deliberately cannot (indefinite or anchored on an event QGP does not
hold), and which are **blockers** — prose that names two periods or makes the
period conditional, where no honest single number exists until a steward decides.

STEWARD-14 (2026-08-10) cleared the last fourteen. Classification therefore runs
through ``library_steward_retention.resolve_category_retention``: an accepted
decision in ``specs/governance-library/steward_retention_decisions.json`` wins,
and the CUT-1 prose grammar answers for everything else. The report says which
of the two decided each category, so "executable" never hides *why*.

A decision naming a ``taxonomy_id`` that is not a filable category in
``taxonomy.json`` is reported as an **orphan** and fails the gate. An orphan is
worse than a blocker: it reads like a cleared category while changing nothing.

It is static: it reads two checked-in JSON files and needs no database, so it can
run in CI and in a review without credentials. It never writes, and it never
proposes a number for a blocked category — proposing one is the silent governance
write the product locks forbid.

Usage::

    PYTHONPATH=. python3 -m scripts.governance.library.citation_cutover_readiness
    PYTHONPATH=. python3 -m scripts.governance.library.citation_cutover_readiness --json
    PYTHONPATH=. python3 -m scripts.governance.library.citation_cutover_readiness --fail-on-blockers

``--fail-on-blockers`` exits non-zero while any category still lacks an
executable retention (or any decision is orphaned). CUT-1 left it opt-in because
the decisions were a pending business input; CIT-1 wires it into ``CI - Default``
now that they have been accepted, so a taxonomy edit that re-opens a blocker
fails the build instead of quietly un-retiring Citation for that category.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.domain.services.library_retention_policy import (  # noqa: E402  (path bootstrap above)
    RetentionAnchor,
)
from src.domain.services.library_steward_retention import (  # noqa: E402  (path bootstrap above)
    SOURCE_STEWARD_DECISION,
    SOURCE_TAXONOMY_PROSE,
    STEWARD_DECISIONS_JSON_PATH,
    resolve_category_retention,
    steward_decision_for,
    steward_retention_decisions,
)

TAXONOMY_PATH = REPO_ROOT / "specs" / "governance-library" / "taxonomy.json"

#: Anchors that can ever yield a disposal date inside QGP.
COMPUTABLE_ANCHORS = frozenset({RetentionAnchor.ISSUE.value, RetentionAnchor.SUPERSEDE.value})


def _load_categories() -> list[dict[str, Any]]:
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return [row for row in payload["categories"] if row.get("level") == 2]


def readiness_report() -> dict[str, Any]:
    """Classify every filable (level-2) category by retention computability."""
    computable: list[dict[str, Any]] = []
    not_applicable: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    filable_ids: set[str] = set()

    for row in _load_categories():
        taxonomy_id = row["id"]
        filable_ids.add(taxonomy_id)
        rule = row.get("retention_rule")
        decision = resolve_category_retention(taxonomy_id, rule)
        steward = steward_decision_for(taxonomy_id)
        entry = {
            "taxonomy_id": taxonomy_id,
            "name": row["name"],
            "retention_rule": rule,
            "retention_years": decision.policy.years if decision.policy else None,
            "retention_anchor": decision.policy.anchor.value if decision.policy else None,
            "reason": decision.reason,
            "source": SOURCE_STEWARD_DECISION if steward else SOURCE_TAXONOMY_PROSE,
            "steward_rationale": steward.rationale if steward else None,
        }
        if decision.policy is None:
            blockers.append(entry)
        elif entry["retention_anchor"] in COMPUTABLE_ANCHORS:
            computable.append(entry)
        else:
            not_applicable.append(entry)

    decisions = steward_retention_decisions()
    # A decision for a taxonomy_id no filable category carries is inert: nothing
    # reads it, no category is cleared by it, and the summary would still count
    # it. Reporting it as an orphan is the only way that stays visible.
    orphans = [
        {
            "taxonomy_id": taxonomy_id,
            "retention_years": decision.years,
            "retention_anchor": decision.anchor.value,
            "reason": "not_a_filable_category",
        }
        for taxonomy_id, decision in sorted(decisions.items())
        if taxonomy_id not in filable_ids
    ]
    steward_decided = [row for row in computable + not_applicable if row["source"] == SOURCE_STEWARD_DECISION]

    return {
        "gate": "CUT-1 / ADR-0023 — Citation SoR retirement requires executable retention",
        "taxonomy": str(TAXONOMY_PATH.relative_to(REPO_ROOT)),
        "steward_decisions_file": str(STEWARD_DECISIONS_JSON_PATH.relative_to(REPO_ROOT)),
        "summary": {
            "filable_categories": len(computable) + len(not_applicable) + len(blockers),
            "computable": len(computable),
            "no_disposal_clock": len(not_applicable),
            "blockers": len(blockers),
            "blocker_reasons": dict(sorted(Counter(row["reason"] for row in blockers).items())),
            "steward_decisions": len(decisions),
            "steward_decisions_applied": len(steward_decided),
            "orphan_steward_decisions": len(orphans),
        },
        "computable": computable,
        "no_disposal_clock": not_applicable,
        "blockers": blockers,
        "steward_decided": steward_decided,
        "orphan_steward_decisions": orphans,
    }


def _print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=== CUT-1 Citation cutover readiness (ADR-0023 / F-7 §2) ===\n")
    print(f"Filable (level-2) categories: {summary['filable_categories']}")
    print(f"  executable retention:       {summary['computable']}")
    print(f"  no disposal clock by design:{summary['no_disposal_clock']:>4}  (indefinite / event-anchored)")
    print(f"  steward decision required:  {summary['blockers']}")
    print(
        f"\nAccepted steward decisions: {summary['steward_decisions']} "
        f"({summary['steward_decisions_applied']} applied to a filable category, "
        f"{summary['orphan_steward_decisions']} orphaned)"
    )
    print(f"  {report['steward_decisions_file']}")

    if report["steward_decided"]:
        print("\nSteward-decided categories (prose unchanged; the decision is the reading of it):")
        for row in report["steward_decided"]:
            years = row["retention_years"]
            print(f"  {row['taxonomy_id']:<7} {str(years) + 'y':<4} {row['retention_anchor']:<11} {row['name']}")
            print(f"          rule: {row['retention_rule']!r}")

    if report["orphan_steward_decisions"]:
        print("\nORPHANED DECISIONS — no filable category carries this taxonomy_id, so the")
        print("decision changes nothing while reading as though a category were cleared:")
        for row in report["orphan_steward_decisions"]:
            print(f"  {row['taxonomy_id']:<7} {row['retention_years']}y {row['retention_anchor']}")

    if report["no_disposal_clock"]:
        print("\nNo disposal clock (kept until a human acts — this is a decision, not a gap):")
        for row in report["no_disposal_clock"]:
            print(f"  {row['taxonomy_id']:<7} {row['retention_anchor']:<11} {row['name']}")

    if report["blockers"]:
        print("\nBLOCKERS — prose no single number can represent. A steward records")
        print(f"`retention_years` + `retention_anchor` in {report['steward_decisions_file']};")
        print("nothing is guessed and the prose is not rewritten:")
        for row in report["blockers"]:
            print(f"  {row['taxonomy_id']:<7} {row['reason']:<16} {row['name']}")
            print(f"          rule: {row['retention_rule']!r}")
        print(
            f"\n{summary['blockers']} categor{'y' if summary['blockers'] == 1 else 'ies'} "
            "cannot yet produce a disposal date. Documents filed under them keep "
            "`retention_until` NULL and are never disposal candidates."
        )
    else:
        print("\nNo blockers: every filable category resolves to an executable retention policy.")
        print("The ADR-0023 / F-7 §2 precondition for retiring Citation (ATLAS) as the")
        print("retention authority for the library Register is met for every category.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--fail-on-blockers",
        action="store_true",
        help=(
            "exit 1 while any category still needs a steward retention decision, "
            "or any accepted decision names a taxonomy_id no filable category carries"
        ),
    )
    args = parser.parse_args(argv)

    report = readiness_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    if not args.fail_on_blockers:
        return 0

    summary = report["summary"]
    if summary["blockers"]:
        print(
            f"\n::error::{summary['blockers']} filable categor"
            f"{'y' if summary['blockers'] == 1 else 'ies'} still has no executable retention. "
            "Citation (ATLAS) cannot be retired as the retention authority for it "
            "(ADR-0023 / F-7 §2). Record the decision in "
            f"{report['steward_decisions_file']}."
        )
        return 1
    if summary["orphan_steward_decisions"]:
        print(
            f"\n::error::{summary['orphan_steward_decisions']} accepted steward decision(s) name a "
            "taxonomy_id that is not a filable (level-2) category. The decision changes nothing "
            "but reads as though a category were cleared."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
