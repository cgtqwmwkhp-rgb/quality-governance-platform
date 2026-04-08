#!/usr/bin/env python3
"""
Boundary violation trend accumulator (D09 WCS closure 2026-04-08).

Reads the current boundary enforcement report from docs/evidence/boundary-enforcement-report.json,
appends an entry to docs/evidence/boundary-trend.json, and prints a summary.

Called by:
  - CI import-boundary-check job (on every push/PR)
  - Daily cron job (.github/workflows/boundary-trend.yml)

The trend file provides N-consecutive-run history needed to evidence
a sustained clean boundary enforcement record for WCS D09.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

CURRENT_REPORT = Path("docs/evidence/boundary-enforcement-report.json")
TREND_FILE = Path("docs/evidence/boundary-trend.json")
MAX_HISTORY = 90  # retain 90 entries (≈ 3 months of daily runs)


def main() -> None:
    if not CURRENT_REPORT.exists():
        print(f"[WARN] Current boundary report not found at {CURRENT_REPORT} — skipping trend update")
        sys.exit(0)

    current = json.loads(CURRENT_REPORT.read_text(encoding="utf-8"))

    entry = {
        "recorded_at": datetime.datetime.utcnow().isoformat() + "Z",
        "ci_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "head_sha": os.environ.get("GITHUB_SHA", current.get("head_sha", "local")),
        "violation_count": current.get("violation_count", -1),
        "check_passed": current.get("check_passed", False),
    }

    if TREND_FILE.exists():
        trend = json.loads(TREND_FILE.read_text(encoding="utf-8"))
    else:
        trend = {"entries": [], "description": "Boundary enforcement trend — violation count per CI run"}

    trend["entries"].append(entry)
    # Trim to max history
    trend["entries"] = trend["entries"][-MAX_HISTORY:]
    trend["last_updated"] = entry["recorded_at"]
    trend["total_runs"] = len(trend["entries"])
    trend["consecutive_clean_runs"] = _count_trailing_clean(trend["entries"])

    TREND_FILE.parent.mkdir(parents=True, exist_ok=True)
    TREND_FILE.write_text(json.dumps(trend, indent=2), encoding="utf-8")

    print(f"[OK] Boundary trend updated: {TREND_FILE}")
    print(f"     Total runs in history: {trend['total_runs']}")
    print(f"     Consecutive clean runs: {trend['consecutive_clean_runs']}")
    print(f"     Current violation count: {entry['violation_count']}")


def _count_trailing_clean(entries: list[dict]) -> int:
    """Count how many of the most recent entries have check_passed=True."""
    count = 0
    for entry in reversed(entries):
        if entry.get("check_passed"):
            count += 1
        else:
            break
    return count


if __name__ == "__main__":
    main()
