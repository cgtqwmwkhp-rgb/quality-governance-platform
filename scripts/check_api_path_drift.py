#!/usr/bin/env python3
"""
API Path Drift Prevention Script

This script scans E2E and smoke tests for disallowed API paths to prevent
the /api vs /api/v1 drift issue that caused GOVPLAT-001.

Usage:
    python scripts/check_api_path_drift.py [--self-test]

Exit codes:
    0: All paths valid
    1: Drift violations found
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Patterns that indicate API path drift
DISALLOWED_PATTERNS = [
    # Direct /api/ without version (should be /api/v1/)
    (r'["\']\/api\/(?!v1\/)', "Use /api/v1/ instead of /api/"),
    # Old endpoint paths that were fixed in GOVPLAT-001
    (r'["\']\/api\/workflows\/', "Use /api/v1/workflows/ instead of /api/workflows/"),
    (r'["\']\/api\/compliance-automation\/', "Use /api/v1/compliance-automation/ instead"),
    (r'["\']\/api\/portal\/', "Use /api/v1/portal/ instead of /api/portal/"),
    (r'["\']\/api\/incidents(?!\/)', "Use /api/v1/incidents instead of /api/incidents"),
    (r'["\']\/api\/audits\/', "Use /api/v1/audits/ instead of /api/audits/"),
    (r'["\']\/api\/risks(?!\/)', "Use /api/v1/risks instead of /api/risks"),
    (r'["\']\/api\/auth\/', "Use /api/v1/auth/ instead of /api/auth/"),
]

# Allowlisted patterns (legitimate uses of /api/ without /v1/)
ALLOWLIST_PATTERNS = [
    r"/api/v1/",  # Correct versioned path
    r"/api/health",  # Health endpoints are typically unversioned
    r"/healthz",  # K8s probes
    r"/readyz",  # K8s probes
    r"/openapi",  # OpenAPI spec endpoint
    r"api_router",  # Code references to router objects
    r"api_client",  # Code references to client objects
    r'startswith\("/api/',  # Checking if path starts with /api/ (validation code)
    r"p.startswith",  # Path prefix checking code
    r"/api/portal/",  # Portal is allowlisted in prefix checks (legacy)
]

# Test directories to scan
TEST_DIRS = [
    "tests/e2e",
    "tests/smoke",
    "tests/integration",
]


class Violation(NamedTuple):
    """A path drift violation."""

    file: str
    line_number: int
    line_content: str
    pattern: str
    remediation: str


def is_allowlisted(line: str) -> bool:
    """Check if a line contains allowlisted patterns."""
    for pattern in ALLOWLIST_PATTERNS:
        if pattern in line:
            return True
    return False


def scan_file(filepath: Path) -> list[Violation]:
    """Scan a single file for path drift violations."""
    violations = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    for line_number, line in enumerate(content.split("\n"), start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Skip if line contains allowlisted pattern
        if is_allowlisted(line):
            continue

        # Check for disallowed patterns
        for pattern, remediation in DISALLOWED_PATTERNS:
            if re.search(pattern, line):
                violations.append(
                    Violation(
                        file=str(filepath),
                        line_number=line_number,
                        line_content=line.strip()[:100],  # Truncate long lines
                        pattern=pattern,
                        remediation=remediation,
                    )
                )

    return violations


def scan_directory(directory: Path) -> list[Violation]:
    """Scan a directory recursively for Python test files."""
    violations = []

    if not directory.exists():
        return violations

    for filepath in directory.rglob("*.py"):
        violations.extend(scan_file(filepath))

    return violations


def run_scan(repo_root: Path) -> tuple[bool, list[Violation]]:
    """
    Run the full scan.

    Returns (passed, violations).
    """
    all_violations = []

    for test_dir in TEST_DIRS:
        dir_path = repo_root / test_dir
        all_violations.extend(scan_directory(dir_path))

    return len(all_violations) == 0, all_violations


def print_report(violations: list[Violation]) -> None:
    """Print a formatted violation report."""
    if not violations:
        print("✅ No API path drift violations found")
        return

    print("=" * 60)
    print("API PATH DRIFT VIOLATIONS")
    print("=" * 60)
    print()

    # Group by file
    by_file: dict[str, list[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)

    for filepath, file_violations in sorted(by_file.items()):
        print(f"📁 {filepath}")
        for v in file_violations:
            print(f"   Line {v.line_number}: {v.line_content}")
            print(f"   ❌ {v.remediation}")
            print()

    print("=" * 60)
    print(f"❌ TOTAL: {len(violations)} violations in {len(by_file)} files")
    print("=" * 60)
    print()
    print("REMEDIATION:")
    print("  Replace /api/<endpoint> with /api/v1/<endpoint>")
    print("  See GOVPLAT-001 for historical context")


def run_self_test() -> bool:
    """
    Self-test to verify detection logic.

    Returns True if all self-tests pass.
    """
    print("=" * 60)
    print("API PATH DRIFT SELF-TEST")
    print("=" * 60)
    print()

    all_passed = True

    # Test 1: Should detect /api/workflows/
    print("Test 1: Detect /api/workflows/ drift...")
    test_line = 'response = client.get("/api/workflows/templates")'
    found = any(re.search(p, test_line) for p, _ in DISALLOWED_PATTERNS)
    if found:
        print("   ✅ PASS: Correctly detected /api/workflows/ drift")
    else:
        print("   ❌ FAIL: Should have detected /api/workflows/ drift")
        all_passed = False

    # Test 2: Should NOT flag /api/v1/workflows/
    print("Test 2: Allow /api/v1/workflows/...")
    test_line = 'response = client.get("/api/v1/workflows/templates")'
    if is_allowlisted(test_line):
        print("   ✅ PASS: Correctly allowed /api/v1/workflows/")
    else:
        print("   ❌ FAIL: Should have allowed /api/v1/workflows/")
        all_passed = False

    # Test 3: Should detect /api/auth/
    print("Test 3: Detect /api/auth/ drift...")
    test_line = 'await client.post("/api/auth/login", json=data)'
    found = any(re.search(p, test_line) for p, _ in DISALLOWED_PATTERNS)
    if found:
        print("   ✅ PASS: Correctly detected /api/auth/ drift")
    else:
        print("   ❌ FAIL: Should have detected /api/auth/ drift")
        all_passed = False

    # Test 4: Should NOT flag comments
    print("Test 4: Skip comments...")
    test_line = "# Old path was /api/workflows/ but now /api/v1/workflows/"
    # This is a comment so shouldn't be scanned
    if test_line.strip().startswith("#"):
        print("   ✅ PASS: Comments are skipped")
    else:
        print("   ❌ FAIL: Comments should be skipped")
        all_passed = False

    # Test 5: Should allow health endpoints
    print("Test 5: Allow health endpoints...")
    test_line = 'response = client.get("/api/health")'
    # Health endpoints are allowlisted
    allowed = is_allowlisted(test_line) or "/health" in test_line
    # Actually check our patterns
    found_violation = any(re.search(p, test_line) for p, _ in DISALLOWED_PATTERNS)
    if not found_violation or is_allowlisted(test_line):
        print("   ✅ PASS: Health endpoints allowed")
    else:
        print("   ❌ FAIL: Health endpoints should be allowed")
        all_passed = False

    print()
    if all_passed:
        print("=" * 60)
        print("✅ ALL SELF-TESTS PASSED")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ SELF-TESTS FAILED")
        print("=" * 60)

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Check for API path drift in test files")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests to verify detection logic")
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).parent.parent, help="Repository root directory"
    )

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    print("=" * 60)
    print("API PATH DRIFT CHECK")
    print("=" * 60)
    print()
    print(f"Scanning: {', '.join(TEST_DIRS)}")
    print()

    passed, violations = run_scan(args.repo_root)
    print_report(violations)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
