#!/usr/bin/env python3
"""Validate release sign-off artifact for strict production gating."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "release_sha": str,
    "governance_lead": str,
    "governance_lead_approved": bool,
    "cab_chair": str,
    "cab_approved": bool,
    "uat_report_path": str,
    "rollback_drill_path": str,
    "approved_at_utc": str,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release sign-off JSON artifact")
    parser.add_argument("--file", required=True, help="Path to sign-off JSON file")
    parser.add_argument("--sha", required=True, help="Expected release SHA")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: Sign-off file not found: {path}")
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in sign-off file: {exc}")
        return 1

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            print(f"ERROR: Missing required field: {field}")
            return 1
        if not isinstance(data[field], expected_type):
            print(f"ERROR: Field '{field}' must be {expected_type.__name__}")
            return 1
        if expected_type is str and not data[field].strip():
            print(f"ERROR: Field '{field}' cannot be empty")
            return 1

    if data["release_sha"] != args.sha:
        print(f"ERROR: release_sha mismatch. expected={args.sha} actual={data['release_sha']}")
        return 1

    if not data["governance_lead_approved"]:
        print("ERROR: governance_lead_approved must be true")
        return 1

    if not data["cab_approved"]:
        print("ERROR: cab_approved must be true")
        return 1

    print("OK: release sign-off artifact valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
