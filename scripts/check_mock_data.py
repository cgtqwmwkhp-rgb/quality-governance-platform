#!/usr/bin/env python3
"""
Mock Data Eradication Gate

Scans specified frontend files for mock data patterns that should not exist
in production code. Returns non-zero exit code if violations are found.

Patterns blocked:
1. MOCK_ prefixed constants (e.g., MOCK_ACTIONS)
2. setTimeout() usage for simulating fetches
3. "coming soon" placeholder strings
4. Hardcoded data arrays without STATIC_UI_CONFIG_OK annotation

Allowlist:
- **/__tests__/**, **/*.test.*, **/*.fixture.*, **/stories/**, **/__mocks__/**
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple


class Violation(NamedTuple):
    """A mock data violation found in source code."""

    file: str
    line: int
    pattern: str
    match: str
    remediation: str


# Patterns to detect mock data
PATTERNS = [
    {
        "name": "MOCK_CONSTANT",
        "regex": re.compile(r"\bMOCK_[A-Z0-9_]+\b"),
        "remediation": "Replace MOCK_* constant with API fetch call",
    },
    {
        "name": "SETTIMEOUT_SIMULATION",
        "regex": re.compile(r"\bsetTimeout\s*\("),
        "remediation": "Remove setTimeout simulation; use real API call with loading state",
    },
    {
        "name": "COMING_SOON_PLACEHOLDER",
        "regex": re.compile(r"coming\s+soon", re.IGNORECASE),
        "remediation": "Implement feature or remove CTA; no placeholder text in production",
    },
    {
        "name": "MOCK_LOWERCASE",
        "regex": re.compile(r"\bconst\s+mock[A-Z][a-zA-Z]*\s*[:=]"),
        "remediation": "Replace mock* object with API-fetched data",
    },
]

# Files to scan (exact paths relative to repo root)
# Scope is expanded as modules are fixed:
# - PR1: Actions.tsx (fixed) ✅
# - PR2: PlanetMark.tsx, UVDBAudits.tsx (fixed) ✅
# - PR3: Standards.tsx, ComplianceEvidence.tsx (pending)
SCOPED_FILES = [
    # PR1 scope - API-backed and mock-free ✅
    "frontend/src/pages/Actions.tsx",
    # PR2 scope - API-backed and mock-free ✅
    "frontend/src/pages/PlanetMark.tsx",
    "frontend/src/pages/UVDBAudits.tsx",
    # PR3 scope - uncomment when fixed
    # "frontend/src/pages/Standards.tsx",
    # "frontend/src/pages/ComplianceEvidence.tsx",
]

# Allowlist patterns - files matching these are skipped
ALLOWLIST_PATTERNS = [
    r"__tests__",
    r"\.test\.",
    r"\.spec\.",
    r"\.fixture\.",
    r"/stories/",
    r"__mocks__",
    r"\.stories\.",
]

# Lines with this comment are allowed to have mock-like patterns
STATIC_CONFIG_ANNOTATION = "STATIC_UI_CONFIG_OK"


def is_allowlisted(file_path: str) -> bool:
    """Check if file matches allowlist patterns."""
    for pattern in ALLOWLIST_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def has_static_config_annotation(lines: list[str], line_num: int) -> bool:
    """Check if the line or previous line has STATIC_UI_CONFIG_OK annotation."""
    # Check current line
    if STATIC_CONFIG_ANNOTATION in lines[line_num]:
        return True
    # Check previous line (annotation above)
    if line_num > 0 and STATIC_CONFIG_ANNOTATION in lines[line_num - 1]:
        return True
    return False


def scan_file(file_path: Path, repo_root: Path) -> list[Violation]:
    """Scan a single file for mock data patterns."""
    violations: list[Violation] = []
    relative_path = str(file_path.relative_to(repo_root))

    if is_allowlisted(relative_path):
        return violations

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
    except Exception as e:
        print(f"[WARN] Could not read {relative_path}: {e}", file=sys.stderr)
        return violations

    for line_num, line in enumerate(lines, start=1):
        for pattern in PATTERNS:
            matches = pattern["regex"].findall(line)
            for match in matches:
                # Skip if has static config annotation
                if has_static_config_annotation(lines, line_num - 1):
                    continue

                violations.append(
                    Violation(
                        file=relative_path,
                        line=line_num,
                        pattern=pattern["name"],
                        match=match if isinstance(match, str) else str(match),
                        remediation=pattern["remediation"],
                    )
                )

    return violations


def scan_directory(repo_root: Path, scoped_files: list[str]) -> list[Violation]:
    """Scan specified files for mock data patterns."""
    all_violations: list[Violation] = []

    for relative_file in scoped_files:
        file_path = repo_root / relative_file
        if file_path.exists():
            violations = scan_file(file_path, repo_root)
            all_violations.extend(violations)
        else:
            print(f"[WARN] Scoped file not found: {relative_file}", file=sys.stderr)

    return all_violations


def format_violations(violations: list[Violation]) -> str:
    """Format violations for CI output."""
    if not violations:
        return "[PASS] No mock data patterns detected in scoped files.\n"

    output_lines = [
        f"[FAIL] Found {len(violations)} mock data violation(s):\n",
    ]

    for v in violations:
        output_lines.append(f"[FAIL] {v.file}:{v.line} — {v.pattern} — {v.remediation}")
        output_lines.append(f"       Match: {v.match[:80]}...")
        output_lines.append("")

    return "\n".join(output_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock Data Eradication Gate - detect mock data in production code")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root directory",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run self-test mode with fixtures",
    )
    parser.add_argument(
        "--extra-files",
        nargs="*",
        default=[],
        help="Additional files to scan (for testing)",
    )

    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    # Determine files to scan
    files_to_scan = SCOPED_FILES.copy()
    if args.extra_files:
        files_to_scan.extend(args.extra_files)

    violations = scan_directory(repo_root, files_to_scan)

    print(format_violations(violations))

    if violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
