#!/usr/bin/env python3
"""Northern Star W9 / NS-NIGHTLY — R08 / R25 / R30 honesty reports (never writes).

Reads ``specs/governance-library/northern-star-v6.json`` and reports estate
honesty for the nightly-enforced warn/alert rules:

- **R08** — every L2 Policy has ≥1 child at L3+ (Statements / Strategy·Plan exempt)
- **R25** — Issued documents need a review date before overdue alerting can fire
- **R30** — every legacy reference resolves to exactly one live PEL; controlled
  documents without a ``legacy_ref`` are coverage gaps (master plan expects
  ~135; the pack currently measures higher — report the real number)

No database sessions. No silent writes. Delivery guard mode refuses fabricated
zeros against ``docs/governance/library_ns_nightly_honesty_baseline.json``.

Usage:
    python -m scripts.governance.library.northern_star_nightly_honesty
    python -m scripts.governance.library.northern_star_nightly_honesty --json
    python -m scripts.governance.library.northern_star_nightly_honesty --guard
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACK_PATH = _REPO_ROOT / "specs" / "governance-library" / "northern-star-v6.json"
_BASELINE_PATH = _REPO_ROOT / "docs" / "governance" / "library_ns_nightly_honesty_baseline.json"

_CHILD_OF = "Child of"
_POLICY = "Policy"
_R08_EXEMPT_TYPES = frozenset({"Statement", "Strategy / Plan"})
_LEGACY_TOKEN_RE = re.compile(
    r"\b(?:(?:IMS|PLA|PXL|MSF|MAN|PP)\s*[-_]?\s*\d+(?:\.\d+)?)|(?:000\d)\b",
    re.IGNORECASE,
)


@dataclass
class Finding:
    code: str
    severity: str  # Critical | Major | Minor | Info | Warn | Alert
    message: str
    refs: list[str] = field(default_factory=list)


@dataclass
class HonestyReport:
    pack_path: str
    document_count: int
    findings: list[Finding] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def writes(self) -> bool:
        """Nightly honesty never mutates — exposed for delivery guard."""
        return False


def load_pack(path: Path | None = None) -> dict[str, Any]:
    pack_path = path or _PACK_PATH
    return json.loads(pack_path.read_text(encoding="utf-8"))


def load_baseline(path: Path | None = None) -> dict[str, Any]:
    baseline_path = path or _BASELINE_PATH
    return json.loads(baseline_path.read_text(encoding="utf-8"))


def normalize_legacy_token(raw: str) -> str:
    token = re.sub(r"[-_]+", " ", (raw or "").strip().upper())
    token = re.sub(r"\s+", " ", token)
    token = re.sub(r"^(IMS|PLA|PXL|MSF|MAN|PP)(\d)", r"\1 \2", token)
    return token


def _level(doc: dict[str, Any]) -> int | None:
    raw = doc.get("level_num")
    if raw is None:
        raw = doc.get("level")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _children_by_parent(pack: dict[str, Any]) -> dict[str, set[str]]:
    children: dict[str, set[str]] = defaultdict(set)
    for rel in pack.get("relationships") or []:
        if rel.get("type") != _CHILD_OF or rel.get("target_kind") != "document":
            continue
        parent = rel.get("to")
        child = rel.get("from")
        if parent and child:
            children[str(parent)].add(str(child))
    for doc in pack.get("documents") or []:
        parent = doc.get("parent_ref")
        ref = doc.get("pel_ref")
        if parent and ref:
            children[str(parent)].add(str(ref))
    return children


def _legacy_resolution_map(docs: list[dict[str, Any]]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for doc in docs:
        legacy = doc.get("legacy_ref")
        if not legacy:
            continue
        ref = str(doc.get("pel_ref") or "")
        for part in re.split(r"[;,/|]+", str(legacy)):
            part = part.strip()
            if not part or part.lower() in {"none", "n/a", "-", "null"}:
                continue
            mapping[normalize_legacy_token(part)].add(ref)
    return mapping


def _legacy_catalogue(docs: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for doc in docs:
        legacy = doc.get("legacy_ref")
        if legacy:
            for part in re.split(r"[;,/|]+", str(legacy)):
                part = part.strip()
                if part and part.lower() not in {"none", "n/a", "-", "null"}:
                    tokens.add(normalize_legacy_token(part))
        blob = " ".join(str(doc.get(k) or "") for k in ("filename", "proposed_filename", "title", "source_location"))
        for match in _LEGACY_TOKEN_RE.findall(blob):
            tokens.add(normalize_legacy_token(match))
    return tokens


def run_honesty_report(pack: dict[str, Any], *, pack_path: Path = _PACK_PATH) -> HonestyReport:
    docs = list(pack.get("documents") or [])
    by_ref = {str(d.get("pel_ref")): d for d in docs if d.get("pel_ref")}
    children = _children_by_parent(pack)
    report = HonestyReport(pack_path=str(pack_path), document_count=len(docs))
    report.counters["documents"] = len(docs)
    report.notes.append("NO WRITES — pack honesty only; does not open a DB session")

    # --- R08: Policies must be implemented ---
    r08_gaps: list[str] = []
    r08_exempt = 0
    for doc in docs:
        if doc.get("type") in _R08_EXEMPT_TYPES and _level(doc) == 2:
            r08_exempt += 1
            continue
        if doc.get("type") != _POLICY or _level(doc) != 2:
            continue
        ref = str(doc.get("pel_ref") or "")
        deep = [child for child in children.get(ref, ()) if child in by_ref and (_level(by_ref[child]) or 0) >= 3]
        if not deep:
            r08_gaps.append(ref)
    report.counters["r08_policy_l2"] = sum(1 for d in docs if d.get("type") == _POLICY and _level(d) == 2)
    report.counters["r08_exempt_l2_statement_strategy"] = r08_exempt
    report.counters["r08_gaps"] = len(r08_gaps)
    if r08_gaps:
        report.findings.append(
            Finding(
                code="R08",
                severity="Warn",
                message=(
                    f"{len(r08_gaps)} L2 Policy document(s) have no child at L3+ " "(Statements / Strategy·Plan exempt)"
                ),
                refs=sorted(r08_gaps)[:40],
            )
        )
    else:
        report.findings.append(
            Finding(
                code="R08",
                severity="Info",
                message="No R08 gaps in pack (unexpected for current estate — verify)",
            )
        )

    # --- R25: Review overdue alerting honesty ---
    issued = [d for d in docs if str(d.get("status") or "").strip().lower() == "issued"]
    issued_missing_review_date = [d for d in issued if not d.get("review_date")]
    all_missing_review_date = sum(1 for d in docs if not d.get("review_date"))
    report.counters["r25_issued"] = len(issued)
    report.counters["r25_issued_with_review_cycle"] = sum(1 for d in issued if d.get("review_cycle_months"))
    report.counters["r25_issued_missing_review_date"] = len(issued_missing_review_date)
    report.counters["r25_pack_missing_review_date"] = all_missing_review_date
    report.counters["r25_overdue_computed"] = 0  # cannot invent overdue without dates
    report.notes.append(
        "R25: pack has no review_date values — overdue count is intentionally "
        "uncomputed (0) and must not be read as 'none overdue'"
    )
    report.findings.append(
        Finding(
            code="R25",
            severity="Alert",
            message=(
                f"{len(issued_missing_review_date)}/{len(issued)} Issued document(s) "
                "lack review_date; nightly owner alerts cannot fire honestly"
            ),
            refs=[str(d.get("pel_ref")) for d in issued_missing_review_date[:40]],
        )
    )

    # --- R30: Legacy references resolve ---
    resolution = _legacy_resolution_map(docs)
    catalogue = _legacy_catalogue(docs)
    unresolved: list[str] = []
    ambiguous: list[str] = []
    resolved_ok = 0
    for token in sorted(catalogue):
        pels = resolution.get(token) or set()
        if len(pels) == 1:
            resolved_ok += 1
        elif len(pels) > 1:
            ambiguous.append(token)
        else:
            unresolved.append(token)
    coverage_gaps = [
        str(d.get("pel_ref"))
        for d in docs
        if d.get("delivery") == "Controlled document"
        and not d.get("external_origin")
        and not str(d.get("legacy_ref") or "").strip()
    ]
    report.counters["r30_catalogue_tokens"] = len(catalogue)
    report.counters["r30_resolved_ok"] = resolved_ok
    report.counters["r30_unresolved_tokens"] = len(unresolved)
    report.counters["r30_ambiguous_tokens"] = len(ambiguous)
    report.counters["r30_resolution_gaps"] = len(unresolved) + len(ambiguous)
    report.counters["r30_register_coverage_gaps"] = len(coverage_gaps)
    # Primary honesty total used by delivery guard / master-plan "~135" note.
    report.counters["r30_gap_total"] = len(coverage_gaps)
    report.notes.append(
        "R30: r30_gap_total = controlled non-external docs missing legacy_ref "
        "(master plan planning estimate ~135; pack measures the honest count)"
    )
    if unresolved or ambiguous:
        report.findings.append(
            Finding(
                code="R30",
                severity="Warn",
                message=(
                    f"{len(unresolved)} unresolved + {len(ambiguous)} ambiguous " "legacy token(s) in pack catalogue"
                ),
                refs=(unresolved + ambiguous)[:40],
            )
        )
    report.findings.append(
        Finding(
            code="R30",
            severity="Warn",
            message=(
                f"{len(coverage_gaps)} controlled document(s) lack legacy_ref "
                "(register coverage gaps; expect ~135 per master plan)"
            ),
            refs=sorted(coverage_gaps)[:40],
        )
    )

    return report


def render_text(report: HonestyReport) -> str:
    lines = [
        "Northern Star nightly honesty (W9 / NS-NIGHTLY) — NO WRITES",
        f"Pack: {report.pack_path}",
        f"Documents: {report.document_count}",
        f"Counters: {json.dumps(report.counters, sort_keys=True)}",
        "",
        "Notes:",
    ]
    for note in report.notes:
        lines.append(f"  - {note}")
    lines.append("")
    lines.append(f"Findings ({len(report.findings)}):")
    if not report.findings:
        lines.append("  (none)")
    for finding in report.findings:
        ref_bit = f" refs={finding.refs[:12]}" if finding.refs else ""
        lines.append(f"  [{finding.severity}] {finding.code}: {finding.message}{ref_bit}")
    lines.append("")
    lines.append("Delivery: use --guard to refuse fabricated zeros against the honesty baseline.")
    return "\n".join(lines) + "\n"


def assert_delivery_guard(
    report: HonestyReport,
    baseline: dict[str, Any] | None = None,
) -> list[str]:
    """Return CRITICAL honesty failures (empty list = pass).

    Fails closed on silent-green: if the pack still has known estate debt, a
    report that claims zero R08/R25/R30 gaps is a delivery defect.
    """
    base = baseline if baseline is not None else load_baseline()
    failures: list[str] = []
    if report.writes:
        failures.append("CRITICAL: honesty report must never write")

    floors = {
        "r08_gaps": int(base.get("r08_gaps_floor", 1)),
        "r25_issued_missing_review_date": int(base.get("r25_issued_missing_review_date_floor", 1)),
        "r30_gap_total": int(base.get("r30_gap_total_floor", 100)),
    }
    for key, floor in floors.items():
        value = int(report.counters.get(key, 0))
        if value < floor:
            failures.append(f"CRITICAL: {key}={value} below honesty floor {floor} " "(fabricated clean / silent green)")

    # Overdue must not be marketed as measured when review dates are absent.
    if (
        int(report.counters.get("r25_pack_missing_review_date", 0)) > 0
        and int(report.counters.get("r25_overdue_computed", -1)) != 0
    ):
        failures.append("CRITICAL: r25_overdue_computed must stay 0 while pack review_date is absent")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=_PACK_PATH, help="Path to northern-star-v6.json")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=_BASELINE_PATH,
        help="Honesty delivery-guard baseline JSON",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report on stdout")
    parser.add_argument(
        "--guard",
        action="store_true",
        help="Delivery guard: exit 1 if counters fall below honesty floors",
    )
    args = parser.parse_args(argv)

    pack = load_pack(args.pack)
    report = run_honesty_report(pack, pack_path=args.pack)

    if args.guard:
        failures = assert_delivery_guard(report, load_baseline(args.baseline))
        payload = {
            "report": asdict(report),
            "guard_failures": failures,
            "guard_ok": not failures,
        }
        if args.json:
            json.dump(payload, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            sys.stdout.write(render_text(report))
            if failures:
                sys.stdout.write("\nDelivery guard FAILURES:\n")
                for item in failures:
                    sys.stdout.write(f"  - {item}\n")
            else:
                sys.stdout.write("\nDelivery guard: OK (honesty floors held)\n")
        return 1 if failures else 0

    if args.json:
        json.dump(asdict(report), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report))
    # Report mode always exits 0 — gaps are expected Warn/Alert, not CI blockers.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
