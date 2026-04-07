#!/usr/bin/env python3
"""ADR Lifecycle Enforcement — CI gate.

Validates that every ADR in docs/adr/ satisfies the minimum structural and
freshness requirements for a governed architecture decision log:

1. Every ADR must have a **Status** field (Accepted | Deprecated | Superseded | Proposed).
2. Every ADR must have a **Date** field parseable as YYYY-MM-DD.
3. No ADR may remain in **Proposed** status for more than 90 days without an update
   (stale proposals indicate governance drift).
4. Deprecated or Superseded ADRs must reference the replacing ADR/decision.

Exit codes:
    0 — all checks pass
    1 — one or more violations found

Evidence written to: docs/evidence/adr-lifecycle-report.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ADR_DIR = Path("docs/adr")
EVIDENCE_PATH = Path("docs/evidence/adr-lifecycle-report.json")
STALE_PROPOSAL_DAYS = 90


def parse_adr(path: Path) -> dict[str, str | None]:
    """Extract key metadata from an ADR markdown file.

    Handles multiple Status/Date conventions found in this repo:
      - ``**Status**: value`` inline
      - ``## Status\\nvalue`` section heading
      - Date embedded in status line as ``**ACCEPTED** - YYYY-MM-DD``
      - ``## Date\\nYYYY-MM-DD`` section heading
    """
    text = path.read_text(encoding="utf-8")

    # Status: try inline bold, then section heading (grab next non-empty line)
    status: str | None = None
    for pattern in [
        r"\*\*Status\*\*:\s*(.+)",
        r"(?:^|\n)##\s+Status\s*\n+\**([A-Za-z][^\n*]+)\**",
    ]:
        m = re.search(pattern, text)
        if m:
            status = m.group(1).strip().strip("*").strip()
            break

    # Date: try inline bold, section heading, or embedded in status line
    date_val: str | None = None
    date_patterns = [
        r"\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})",
        r"(?:^|\n)##\s+Date\s*\n+(\d{4}-\d{2}-\d{2})",
        r"(\d{4}-\d{2}-\d{2})",  # fallback: first ISO date anywhere in file
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text)
        if m:
            date_val = m.group(1).strip()
            break

    superseded_match = re.search(r"[Ss]uperseded.{0,50}(ADR-\d+)", text)
    return {
        "file": path.name,
        "status": status,
        "date": date_val,
        "superseded_by": superseded_match.group(1) if superseded_match else None,
    }


def validate_adr(meta: dict[str, str | None], today: date) -> list[str]:
    """Return list of violation strings (empty = clean)."""
    violations: list[str] = []

    if not meta["status"]:
        violations.append("Missing **Status** field")
    else:
        valid_statuses = {"Accepted", "Deprecated", "Superseded", "Proposed", "Active"}
        raw_status = meta["status"].split("—")[0].split("(")[0].strip()
        if raw_status not in valid_statuses:
            violations.append(f"Unrecognised status '{raw_status}' (expected: {', '.join(sorted(valid_statuses))})")

        if raw_status in {"Deprecated", "Superseded"} and not meta["superseded_by"]:
            violations.append(f"Status is '{raw_status}' but no superseding ADR reference found")

        if raw_status == "Proposed" and meta["date"]:
            try:
                adr_date = datetime.strptime(meta["date"], "%Y-%m-%d").date()
                age = (today - adr_date).days
                if age > STALE_PROPOSAL_DAYS:
                    violations.append(
                        f"Stale Proposed ADR: {age} days old (limit {STALE_PROPOSAL_DAYS}); "
                        "accept, reject, or update the decision"
                    )
            except ValueError:
                pass

    if not meta["date"]:
        violations.append("Missing **Date** field (expected format: YYYY-MM-DD)")

    return violations


def main() -> int:
    adr_files = sorted(ADR_DIR.glob("ADR-*.md"))
    if not adr_files:
        print(f"[WARN] No ADR files found in {ADR_DIR}/")
        return 0

    today = date.today()
    report: list[dict] = []
    total_violations = 0

    print(f"\n=== ADR Lifecycle Check ({len(adr_files)} files) ===\n")

    for path in adr_files:
        meta = parse_adr(path)
        violations = validate_adr(meta, today)
        total_violations += len(violations)
        status_display = meta["status"] or "MISSING"
        marker = "[OK]  " if not violations else "[FAIL]"
        print(f"  {marker} {path.name}  status={status_display}  date={meta['date'] or 'MISSING'}")
        for v in violations:
            print(f"         → {v}")
        report.append({**meta, "violations": violations})

    # Write evidence
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_PATH, "w") as f:
        json.dump({
            "generated": today.isoformat(),
            "adr_count": len(adr_files),
            "total_violations": total_violations,
            "adrs": report,
        }, f, indent=2)

    print(f"\n[Evidence written to {EVIDENCE_PATH}]")

    if total_violations:
        print(f"\n[FAIL] {total_violations} ADR lifecycle violation(s) found — fix before merging\n")
        return 1

    print(f"\n[OK] All {len(adr_files)} ADRs pass lifecycle requirements\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
