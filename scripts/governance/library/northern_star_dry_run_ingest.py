#!/usr/bin/env python3
"""Northern Star W5b / NS-2 — dry-run ingest report (never writes).

Reads ``specs/governance-library/northern-star-v6.json`` and reports what an
index/upload wave would see: document counts, R01–R03 / R26 / R32 identity
checks, Supersedes self-loops, and multiple Child-of parents.

Usage:
    python -m scripts.governance.library.northern_star_dry_run_ingest
    python -m scripts.governance.library.northern_star_dry_run_ingest --json

Exit codes:
    0 — report produced; no Critical blockers for a steward dry-run review
    1 — Critical findings present (self-loops, R01 failures, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.domain.exceptions import ValidationError
from src.domain.services.library_rules import (
    assert_access_level_required,
    assert_filename_grammar_if_pel_prefixed,
    assert_pel_identity,
    reference_pattern,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACK_PATH = _REPO_ROOT / "specs" / "governance-library" / "northern-star-v6.json"

# Child-of convention in the pack: ``from`` = child, ``to`` = parent
# (parent_ref agrees with this orientation for ~378/388 documents).
_CHILD_OF = "Child of"
_SUPERSEDES = "Supersedes"


@dataclass
class Finding:
    code: str
    severity: str  # Critical | Major | Minor | Info
    message: str
    refs: list[str] = field(default_factory=list)


@dataclass
class DryRunReport:
    pack_path: str
    document_count: int
    relationship_count: int
    findings: list[Finding] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "Critical")


def load_pack(path: Path | None = None) -> dict[str, Any]:
    pack_path = path or _PACK_PATH
    return json.loads(pack_path.read_text(encoding="utf-8"))


def run_dry_run(pack: dict[str, Any], *, pack_path: Path = _PACK_PATH) -> DryRunReport:
    docs = list(pack.get("documents") or [])
    rels = list(pack.get("relationships") or [])
    report = DryRunReport(
        pack_path=str(pack_path),
        document_count=len(docs),
        relationship_count=len(rels),
    )
    report.counters["documents"] = len(docs)
    report.counters["relationships"] = len(rels)

    if len(docs) != 388:
        report.findings.append(
            Finding(
                code="COUNT",
                severity="Major",
                message=f"Expected 388 Northern Star documents, found {len(docs)}",
            )
        )

    # --- identity per document ---
    r01 = r02 = r03 = r26 = r32 = 0
    for doc in docs:
        ref = str(doc.get("pel_ref") or "")
        function = str(doc.get("function") or "")
        level = doc.get("level_num")
        if level is None:
            level = doc.get("level")
        try:
            level_i = int(level)
        except (TypeError, ValueError):
            report.findings.append(Finding("LEVEL", "Critical", f"Missing/invalid level_num on {ref}", [ref]))
            continue
        try:
            assert_pel_identity(ref, function_code=function, cascade_level=level_i)
        except ValidationError as exc:
            msg = str(exc)
            sev = "Critical"
            if msg.startswith("R01"):
                r01 += 1
            elif msg.startswith("R02"):
                r02 += 1
            elif msg.startswith("R03"):
                r03 += 1
            report.findings.append(Finding(msg[:3], sev, msg, [ref]))

        access = doc.get("access")
        try:
            assert_access_level_required(str(access) if access is not None else None)
        except ValidationError as exc:
            r26 += 1
            report.findings.append(Finding("R26", "Critical", str(exc), [ref]))

        proposed = doc.get("proposed_filename") or doc.get("filename")
        try:
            assert_filename_grammar_if_pel_prefixed(str(proposed) if proposed else None)
        except ValidationError as exc:
            r32 += 1
            report.findings.append(Finding("R32", "Major", str(exc), [ref]))

    report.counters["r01_failures"] = r01
    report.counters["r02_failures"] = r02
    report.counters["r03_failures"] = r03
    report.counters["r26_failures"] = r26
    report.counters["r32_failures"] = r32
    report.counters["r01_ok"] = sum(1 for d in docs if reference_pattern().fullmatch(str(d.get("pel_ref") or "")))

    # --- Supersedes self-loops ---
    self_loops = [
        r
        for r in rels
        if r.get("type") == _SUPERSEDES
        and r.get("target_kind") == "document"
        and r.get("from")
        and r.get("from") == r.get("to")
    ]
    report.counters["supersedes_self_loops"] = len(self_loops)
    if self_loops:
        report.findings.append(
            Finding(
                code="SELF_LOOP",
                severity="Critical",
                message=(
                    f"{len(self_loops)} Supersedes self-loop(s) — a document cannot "
                    "supersede itself; remove before ingest"
                ),
                refs=[str(r["from"]) for r in self_loops],
            )
        )

    # --- multiple Child-of parents (from = child, to = parent) ---
    parents_by_child: dict[str, list[str]] = defaultdict(list)
    for r in rels:
        if r.get("type") != _CHILD_OF or r.get("target_kind") != "document":
            continue
        child = r.get("from")
        parent = r.get("to")
        if child and parent:
            parents_by_child[str(child)].append(str(parent))
    multi = {c: ps for c, ps in parents_by_child.items() if len(set(ps)) > 1}
    report.counters["multi_parent_children"] = len(multi)
    if multi:
        sample = sorted(multi.items())[:14]
        report.findings.append(
            Finding(
                code="SECOND_PARENT",
                severity="Major",
                message=(
                    f"{len(multi)} document(s) have more than one Child-of parent; "
                    "primary parent stays on documents.parent_ref — steward map only"
                ),
                refs=[f"{c}←{','.join(sorted(set(ps)))}" for c, ps in sample],
            )
        )

    # parent_ref vs edges mismatch (info for stewards)
    mismatches = 0
    for doc in docs:
        ref = str(doc.get("pel_ref") or "")
        pref = doc.get("parent_ref")
        if not pref:
            continue
        edge_parents = set(parents_by_child.get(ref) or [])
        if edge_parents and str(pref) not in edge_parents:
            mismatches += 1
    report.counters["parent_ref_edge_mismatches"] = mismatches
    if mismatches:
        report.findings.append(
            Finding(
                code="PARENT_MISMATCH",
                severity="Minor",
                message=f"{mismatches} document(s) have parent_ref not present in Child-of edges",
            )
        )

    by_sev = Counter(f.severity for f in report.findings)
    report.counters.update({f"findings_{k.lower()}": v for k, v in by_sev.items()})
    return report


def render_text(report: DryRunReport) -> str:
    lines = [
        "Northern Star dry-run ingest (W5b / NS-2) — NO WRITES",
        f"Pack: {report.pack_path}",
        f"Documents: {report.document_count}  Relationships: {report.relationship_count}",
        f"Counters: {json.dumps(report.counters, sort_keys=True)}",
        "",
        f"Findings ({len(report.findings)}):",
    ]
    if not report.findings:
        lines.append("  (none)")
    for f in report.findings:
        ref_bit = f" refs={f.refs[:8]}" if f.refs else ""
        lines.append(f"  [{f.severity}] {f.code}: {f.message}{ref_bit}")
    lines.append("")
    lines.append(
        "Critical blockers: "
        + str(report.critical_count)
        + (" — refuse silent ingest" if report.critical_count else " — steward may proceed to confirm/upload")
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack",
        type=Path,
        default=_PACK_PATH,
        help="Path to northern-star-v6.json",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report on stdout")
    args = parser.parse_args(argv)

    pack = load_pack(args.pack)
    report = run_dry_run(pack, pack_path=args.pack)
    if args.json:
        payload = asdict(report)
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report))
    return 1 if report.critical_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
