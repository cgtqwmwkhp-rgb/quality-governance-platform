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
taxonomy category through the one CUT-1 resolver and reports which categories
can produce a disposal date, which deliberately cannot (indefinite or anchored
on an event QGP does not hold), and which are **blockers** — prose that names
two periods or makes the period conditional, where no honest single number
exists until a steward decides.

It is static: it reads ``specs/governance-library/taxonomy.json`` and needs no
database, so it can run in CI and in a review without credentials. It never
writes, and it never proposes a number for a blocked category — proposing one
is the silent governance write the product locks forbid.

Usage::

    PYTHONPATH=. python3 -m scripts.governance.library.citation_cutover_readiness
    PYTHONPATH=. python3 -m scripts.governance.library.citation_cutover_readiness --json

Exit ``0`` always for the report itself. Pass ``--fail-on-blockers`` to make an
unresolved blocker non-zero — deliberately **not** the default, because CUT-1
lands the mechanism and the fourteen steward decisions are a business input, not
a code defect. Wire the flag in when the cutover is scheduled.
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
    resolve_retention_rule,
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

    for row in _load_categories():
        rule = row.get("retention_rule")
        decision = resolve_retention_rule(rule)
        entry = {
            "taxonomy_id": row["id"],
            "name": row["name"],
            "retention_rule": rule,
            "retention_years": decision.policy.years if decision.policy else None,
            "retention_anchor": decision.policy.anchor.value if decision.policy else None,
            "reason": decision.reason,
        }
        if decision.policy is None:
            blockers.append(entry)
        elif entry["retention_anchor"] in COMPUTABLE_ANCHORS:
            computable.append(entry)
        else:
            not_applicable.append(entry)

    return {
        "gate": "CUT-1 / ADR-0023 — Citation SoR retirement requires executable retention",
        "taxonomy": str(TAXONOMY_PATH.relative_to(REPO_ROOT)),
        "summary": {
            "filable_categories": len(computable) + len(not_applicable) + len(blockers),
            "computable": len(computable),
            "no_disposal_clock": len(not_applicable),
            "blockers": len(blockers),
            "blocker_reasons": dict(sorted(Counter(row["reason"] for row in blockers).items())),
        },
        "computable": computable,
        "no_disposal_clock": not_applicable,
        "blockers": blockers,
    }


def _print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=== CUT-1 Citation cutover readiness (ADR-0023 / F-7 §2) ===\n")
    print(f"Filable (level-2) categories: {summary['filable_categories']}")
    print(f"  executable retention:       {summary['computable']}")
    print(f"  no disposal clock by design:{summary['no_disposal_clock']:>4}  (indefinite / event-anchored)")
    print(f"  steward decision required:  {summary['blockers']}")

    if report["no_disposal_clock"]:
        print("\nNo disposal clock (kept until a human acts — this is a decision, not a gap):")
        for row in report["no_disposal_clock"]:
            print(f"  {row['taxonomy_id']:<7} {row['retention_anchor']:<11} {row['name']}")

    if report["blockers"]:
        print("\nBLOCKERS — prose no single number can represent. A steward sets")
        print("`retention_years` + `retention_anchor` on the category; nothing is guessed:")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--fail-on-blockers",
        action="store_true",
        help="exit 1 while any category still needs a steward retention decision",
    )
    args = parser.parse_args(argv)

    report = readiness_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    if args.fail_on_blockers and report["summary"]["blockers"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
