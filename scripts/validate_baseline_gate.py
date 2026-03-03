#!/usr/bin/env python3
"""
Baseline Gate Validator - Single Source of Truth Enforcement

This script reads the baseline from docs/evidence/e2e_baseline.json and
validates that the current test run meets the minimum acceptable threshold.

Exit codes:
  0 - Gate passed
  1 - Gate failed (regression detected)
  2 - Configuration error (missing baseline file, invalid JSON, etc.)
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class BaselineConfig:
    """Baseline configuration from single source of truth."""

    baseline_pass_count: int
    baseline_skip_count: int
    baseline_total_count: int
    baseline_commit_sha: str
    baseline_date: str
    baseline_notes: str
    version: str
    min_acceptable_percentage: int
    override: Optional[dict]


@dataclass
class Override:
    """Structured override with required fields."""

    issue_id: str
    owner: str
    expiry: str  # ISO 8601 date
    reason: str
    temporary_min_pass: int


def load_baseline(baseline_path: Path) -> BaselineConfig:
    """Load baseline from the single source of truth file."""
    if not baseline_path.exists():
        print(f"❌ GATE ERROR: Baseline file not found: {baseline_path}")
        print("   The baseline file is the single source of truth and MUST exist.")
        sys.exit(2)

    try:
        with open(baseline_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ GATE ERROR: Invalid JSON in baseline file: {e}")
        sys.exit(2)

    required_fields = [
        "baseline_pass_count",
        "baseline_skip_count",
        "baseline_total_count",
        "baseline_commit_sha",
        "baseline_date",
        "baseline_notes",
        "version",
        "min_acceptable_percentage",
    ]

    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ GATE ERROR: Missing required fields in baseline: {missing}")
        sys.exit(2)

    return BaselineConfig(
        baseline_pass_count=data["baseline_pass_count"],
        baseline_skip_count=data["baseline_skip_count"],
        baseline_total_count=data["baseline_total_count"],
        baseline_commit_sha=data["baseline_commit_sha"],
        baseline_date=data["baseline_date"],
        baseline_notes=data["baseline_notes"],
        version=data["version"],
        min_acceptable_percentage=data["min_acceptable_percentage"],
        override=data.get("override"),
    )


def parse_override(override_data: Optional[dict]) -> Optional[Override]:
    """Parse and validate override data."""
    if override_data is None:
        return None

    required = ["issue_id", "owner", "expiry", "reason", "temporary_min_pass"]
    missing = [f for f in required if f not in override_data]

    if missing:
        print(f"⚠️  WARNING: Override present but missing required fields: {missing}")
        print("   Override will be ignored. Required: issue_id, owner, expiry, reason, temporary_min_pass")
        return None

    # Check expiry
    try:
        expiry_date = datetime.fromisoformat(override_data["expiry"])
        if expiry_date.date() < datetime.now().date():
            print(f"⚠️  WARNING: Override expired on {override_data['expiry']}")
            print(f"   Owner: {override_data['owner']}, Issue: {override_data['issue_id']}")
            print("   Override will be ignored. Update the expiry or remove the override.")
            return None
    except ValueError:
        print(f"⚠️  WARNING: Invalid expiry date format: {override_data['expiry']}")
        print("   Expected ISO 8601 format (YYYY-MM-DD). Override will be ignored.")
        return None

    return Override(
        issue_id=override_data["issue_id"],
        owner=override_data["owner"],
        expiry=override_data["expiry"],
        reason=override_data["reason"],
        temporary_min_pass=override_data["temporary_min_pass"],
    )


def compute_min_acceptable(baseline: BaselineConfig, override: Optional[Override]) -> int:
    """Compute minimum acceptable pass count."""
    if override:
        return override.temporary_min_pass

    return int(baseline.baseline_pass_count * baseline.min_acceptable_percentage / 100)


def validate_gate(current_passed: int, current_skipped: int, baseline_path: Path) -> bool:
    """
    Validate the baseline gate.

    Returns True if gate passes, False if it fails.
    Exits with code 2 on configuration errors.
    """
    print("=" * 70)
    print("BASELINE GATE VALIDATION")
    print("=" * 70)
    print()

    # Load baseline from single source of truth
    baseline = load_baseline(baseline_path)

    print(f"📋 Baseline Source: {baseline_path}")
    print(f"   Version: {baseline.version}")
    print(f"   Commit: {baseline.baseline_commit_sha}")
    print(f"   Date: {baseline.baseline_date}")
    print(f"   Notes: {baseline.baseline_notes}")
    print()
    print(f"📊 Baseline Values (from artifact):")
    print(f"   Baseline Pass Count: {baseline.baseline_pass_count}")
    print(f"   Baseline Skip Count: {baseline.baseline_skip_count}")
    print(f"   Baseline Total Count: {baseline.baseline_total_count}")
    print(f"   Min Acceptable Percentage: {baseline.min_acceptable_percentage}%")
    print()

    # Check for override
    override = parse_override(baseline.override)
    if override:
        print(f"⚠️  OVERRIDE ACTIVE:")
        print(f"   Issue ID: {override.issue_id}")
        print(f"   Owner: {override.owner}")
        print(f"   Expiry: {override.expiry}")
        print(f"   Reason: {override.reason}")
        print(f"   Temporary Min Pass: {override.temporary_min_pass}")
        print()

    # Compute threshold
    min_acceptable = compute_min_acceptable(baseline, override)

    print(f"📏 Computed Threshold:")
    if override:
        print(f"   MIN_ACCEPTABLE = {min_acceptable} (from override)")
    else:
        print(
            f"   MIN_ACCEPTABLE = {baseline.baseline_pass_count} × {baseline.min_acceptable_percentage}% = {min_acceptable}"
        )
    print()

    print(f"🧪 Current Run:")
    print(f"   Passed: {current_passed}")
    print(f"   Skipped: {current_skipped}")
    print()

    # Gate decision
    if current_passed >= min_acceptable:
        print("=" * 70)
        print(f"✅ BASELINE GATE PASSED")
        print(f"   {current_passed} >= {min_acceptable} (min acceptable)")
        print("=" * 70)
        return True
    else:
        print("=" * 70)
        print(f"❌ BASELINE GATE FAILED - REGRESSION DETECTED")
        print(f"   {current_passed} < {min_acceptable} (min acceptable)")
        print()
        print(f"   Deficit: {min_acceptable - current_passed} tests below threshold")
        print()
        print("   To resolve:")
        print("   1. Fix the failing tests, OR")
        print("   2. Add a structured override to docs/evidence/e2e_baseline.json with:")
        print('      "override": {')
        print('        "issue_id": "GH-XXX",')
        print('        "owner": "your-github-handle",')
        print('        "expiry": "YYYY-MM-DD",')
        print('        "reason": "Detailed justification",')
        print('        "temporary_min_pass": <new_threshold>')
        print("      }")
        print("=" * 70)
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate E2E test results against baseline gate")
    parser.add_argument("--passed", type=int, required=True, help="Number of tests that passed")
    parser.add_argument("--skipped", type=int, default=0, help="Number of tests that were skipped")
    parser.add_argument(
        "--baseline-file",
        type=str,
        default="docs/evidence/e2e_baseline.json",
        help="Path to baseline JSON file (default: docs/evidence/e2e_baseline.json)",
    )

    args = parser.parse_args()

    baseline_path = Path(args.baseline_file)
    if not baseline_path.is_absolute():
        # Look relative to repo root
        repo_root = Path(__file__).parent.parent
        baseline_path = repo_root / baseline_path

    passed = validate_gate(args.passed, args.skipped, baseline_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
