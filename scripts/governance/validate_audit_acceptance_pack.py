#!/usr/bin/env python3
"""Validate required evidence artifacts for final audit acceptance."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_FILES = [
    "docs/contracts/AUDIT_LIFECYCLE_CONTRACT.md",
    "docs/runbooks/AUDIT_OBSERVABILITY_ALERTS.md",
    "docs/runbooks/AUDIT_STRICT_RELEASE_GATES.md",
    "docs/runbooks/AUDIT_ROLLBACK_DRILL.md",
    "docs/uat/AUDIT_WORLD_CLASS_UAT_CAB_RUNBOOK.md",
    "docs/evidence/WORLD_LEADING_AUDIT_ACCEPTANCE_PACK_TEMPLATE.md",
    "docs/evidence/UAT_CAB_SIGNOFF_REPORT_TEMPLATE.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate required acceptance-pack artifacts")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.repo_root)
    missing: list[str] = []
    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            missing.append(rel)

    if missing:
        print("ERROR: Missing required acceptance artifacts:")
        for item in missing:
            print(f"- {item}")
        return 1

    print("OK: Acceptance-pack artifacts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
