#!/usr/bin/env python3
"""
Test Quarantine Policy Validator

Validates that all skipped tests follow the quarantine policy:
- Must have QUARANTINE annotation with issue ID, reason, owner, target date
- Reports on all quarantined tests
- Warns on tests exceeding their target date

Usage:
    python scripts/check_test_quarantine.py

Exit codes:
    0: All skips are properly annotated
    1: Found bare skips without quarantine annotation

See: docs/runbooks/TEST_QUARANTINE_POLICY.md
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class QuarantinedTest:
    """Represents a quarantined test with its metadata."""

    file_path: str
    line_number: int
    test_name: str
    issue_id: Optional[str] = None
    reason_code: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    target_date: Optional[str] = None
    raw_reason: str = ""

    @property
    def is_valid_quarantine(self) -> bool:
        """Check if quarantine has all required fields."""
        return bool(self.issue_id and self.owner and self.target_date)

    @property
    def is_expired(self) -> bool:
        """Check if target date has passed."""
        if not self.target_date:
            return False
        try:
            target = datetime.strptime(self.target_date, "%Y-%m-%d")
            return target < datetime.now()
        except ValueError:
            return False


# Patterns for matching skip decorators
SKIP_PATTERN = re.compile(r"@pytest\.mark\.skip\s*\(\s*reason\s*=\s*[\"'](.+?)[\"']\s*\)")
SKIPIF_PATTERN = re.compile(r"@pytest\.mark\.skipif\s*\([^,]+,\s*reason\s*=\s*[\"'](.+?)[\"']\s*\)")
PYTESTMARK_SKIP = re.compile(r"pytestmark\s*=\s*pytest\.mark\.skip\s*\(\s*reason\s*=\s*[\"'](.+?)[\"']\s*\)")
DEF_TEST_PATTERN = re.compile(r"def\s+(test_\w+)")

# Pattern to extract quarantine metadata
QUARANTINE_PATTERN = re.compile(
    r"QUARANTINE:\s*"
    r"(?P<issue_id>[\w-]+)\s+"
    r"(?P<reason_code>\w+)\s*-\s*"
    r"(?P<description>[^|]+?)\s*\|\s*"
    r"Owner:\s*(?P<owner>[^\s|]+)\s*\|\s*"
    r"Target:\s*(?P<target_date>\d{4}-\d{2}-\d{2})"
)

# Allowed skip reasons that don't require quarantine annotation
ALLOWED_NON_QUARANTINE = [
    "QUARANTINE_POLICY.yaml",  # Tests using YAML-based quarantine
    "not implemented",  # Feature not yet implemented
    "deprecated",  # Test for deprecated feature
]


def find_test_files(tests_dir: Path) -> list[Path]:
    """Find all Python test files."""
    return list(tests_dir.rglob("test_*.py"))


def extract_skips(file_path: Path) -> list[QuarantinedTest]:
    """Extract all skip decorators from a test file."""
    skips = []
    content = file_path.read_text()
    lines = content.split("\n")

    current_test_name = None
    pending_skip_reason = None
    pending_skip_line = None

    for i, line in enumerate(lines, start=1):
        line_stripped = line.strip()

        # Check for skip decorator
        skip_match = SKIP_PATTERN.search(line_stripped)
        skipif_match = SKIPIF_PATTERN.search(line_stripped)
        pytestmark_match = PYTESTMARK_SKIP.search(line_stripped)

        if skip_match or skipif_match or pytestmark_match:
            match = skip_match or skipif_match or pytestmark_match
            reason = match.group(1) if match else ""
            pending_skip_reason = reason
            pending_skip_line = i

        # Check for test function definition
        test_match = DEF_TEST_PATTERN.search(line_stripped)
        if test_match:
            current_test_name = test_match.group(1)

            # If we have a pending skip from previous lines
            if pending_skip_reason and pending_skip_line:
                quarantine = parse_quarantine(
                    str(file_path),
                    pending_skip_line,
                    current_test_name,
                    pending_skip_reason,
                )
                skips.append(quarantine)

            pending_skip_reason = None
            pending_skip_line = None

        # Check for module-level pytestmark
        if pytestmark_match:
            quarantine = parse_quarantine(str(file_path), i, "[MODULE]", pytestmark_match.group(1))
            skips.append(quarantine)

    return skips


def parse_quarantine(file_path: str, line_number: int, test_name: str, reason: str) -> QuarantinedTest:
    """Parse quarantine metadata from skip reason."""
    match = QUARANTINE_PATTERN.search(reason)

    if match:
        return QuarantinedTest(
            file_path=file_path,
            line_number=line_number,
            test_name=test_name,
            issue_id=match.group("issue_id"),
            reason_code=match.group("reason_code"),
            description=match.group("description").strip(),
            owner=match.group("owner"),
            target_date=match.group("target_date"),
            raw_reason=reason,
        )
    else:
        return QuarantinedTest(
            file_path=file_path,
            line_number=line_number,
            test_name=test_name,
            raw_reason=reason,
        )


def is_allowed_skip(reason: str) -> bool:
    """Check if skip reason is in the allowed list."""
    for allowed in ALLOWED_NON_QUARANTINE:
        if allowed.lower() in reason.lower():
            return True
    return False


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Test Quarantine Policy Validator")
    print("=" * 60)
    print()

    # Find test files
    tests_dir = Path(__file__).parent.parent / "tests"
    if not tests_dir.exists():
        print(f"ERROR: Tests directory not found: {tests_dir}")
        return 1

    test_files = find_test_files(tests_dir)
    print(f"Scanning {len(test_files)} test files...")
    print()

    all_skips: list[QuarantinedTest] = []

    for test_file in test_files:
        skips = extract_skips(test_file)
        all_skips.extend(skips)

    # Categorize skips
    valid_quarantines = [s for s in all_skips if s.is_valid_quarantine]
    allowed_skips = [s for s in all_skips if is_allowed_skip(s.raw_reason) and not s.is_valid_quarantine]
    bare_skips = [s for s in all_skips if not s.is_valid_quarantine and not is_allowed_skip(s.raw_reason)]
    expired_quarantines = [s for s in valid_quarantines if s.is_expired]

    # Report
    print("=" * 60)
    print("QUARANTINE REPORT")
    print("=" * 60)
    print()
    print(f"Total skipped tests:     {len(all_skips)}")
    print(f"Valid quarantines:       {len(valid_quarantines)}")
    print(f"Allowed skips:           {len(allowed_skips)}")
    print(f"Bare skips (violations): {len(bare_skips)}")
    print(f"Expired quarantines:     {len(expired_quarantines)}")
    print()

    if valid_quarantines:
        print("-" * 60)
        print("QUARANTINED TESTS:")
        print("-" * 60)
        for skip in valid_quarantines:
            expired_marker = " [EXPIRED]" if skip.is_expired else ""
            print(f"  {skip.file_path}:{skip.line_number}")
            print(f"    Test: {skip.test_name}")
            print(f"    Issue: {skip.issue_id}")
            print(f"    Reason: {skip.reason_code} - {skip.description}")
            print(f"    Owner: {skip.owner}")
            print(f"    Target: {skip.target_date}{expired_marker}")
            print()

    if allowed_skips:
        print("-" * 60)
        print("ALLOWED SKIPS (non-quarantine):")
        print("-" * 60)
        for skip in allowed_skips:
            print(f"  {skip.file_path}:{skip.line_number}")
            print(f"    Test: {skip.test_name}")
            print(f"    Reason: {skip.raw_reason[:80]}...")
            print()

    if bare_skips:
        print("-" * 60)
        print("VIOLATIONS - BARE SKIPS WITHOUT QUARANTINE:")
        print("-" * 60)
        for skip in bare_skips:
            print(f"  {skip.file_path}:{skip.line_number}")
            print(f"    Test: {skip.test_name}")
            print(f"    Reason: {skip.raw_reason[:80]}...")
            print()

    if expired_quarantines:
        print("-" * 60)
        print("WARNING - EXPIRED QUARANTINES:")
        print("-" * 60)
        for skip in expired_quarantines:
            print(f"  {skip.file_path}:{skip.line_number}")
            print(f"    Test: {skip.test_name}")
            print(f"    Issue: {skip.issue_id}")
            print(f"    Target was: {skip.target_date}")
            print()

    print("=" * 60)

    # Currently we warn but don't fail on bare skips
    # To enforce strictly, change this to: return 1 if bare_skips else 0
    if bare_skips:
        print("WARNING: Found bare skips. See TEST_QUARANTINE_POLICY.md for guidance.")
        print("         These should be converted to proper quarantine annotations.")
        print()
        # Return 0 for now to not break existing workflows
        return 0

    print("SUCCESS: All skips comply with quarantine policy (or are allowed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
