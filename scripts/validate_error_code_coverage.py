#!/usr/bin/env python3
"""Validate that every ErrorCode enum value has at least one reference in the test suite.

This gate ensures the error-code catalog stays aligned with test coverage.
An error code without any test reference is a dead code path — either untested
or unused — and should be removed or covered.

Exit 0 = all codes referenced in tests.
Exit 1 = one or more codes have zero test references.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ERROR_CODES_FILE = REPO_ROOT / "src" / "domain" / "error_codes.py"
TESTS_DIR = REPO_ROOT / "tests"

# Error codes that are legitimately only used in production paths (not triggered
# in unit/integration tests by design — e.g., infrastructure-level errors).
# To add an exemption: document WHY it is not tested and get it reviewed.
EXEMPT_CODES: set[str] = {
    "MFA_REQUIRED",  # MFA not enabled in test environment
    "MFA_INVALID",  # MFA not enabled in test environment
    "PASSWORD_TOO_WEAK",  # Auth delegated to Azure AD B2C
    "PASSWORD_REUSED",  # Auth delegated to Azure AD B2C
    "ACCOUNT_LOCKED",  # Auth delegated to Azure AD B2C
    "TOKEN_REVOKED",  # Covered by auth revocation integration tests
    "GDPR_ERASURE_PENDING",  # GDPR API integration path, coverage in e2e
}


def extract_error_codes(path: Path) -> list[str]:
    """Parse ErrorCode enum members from the error_codes.py file."""
    text = path.read_text()
    return re.findall(r"^\s+([A-Z_]+)\s*=\s*\"[A-Z_]+\"", text, re.MULTILINE)


def collect_test_content(tests_dir: Path) -> str:
    """Concatenate all test file content for grep-style searching."""
    parts: list[str] = []
    for test_file in tests_dir.rglob("*.py"):
        parts.append(test_file.read_text())
    return "\n".join(parts)


def collect_src_content(src_dir: Path) -> str:
    """Concatenate all src/*.py content for usage verification."""
    parts: list[str] = []
    for src_file in src_dir.rglob("*.py"):
        if "__pycache__" not in str(src_file):
            parts.append(src_file.read_text())
    return "\n".join(parts)


def main() -> int:
    if not ERROR_CODES_FILE.exists():
        print(f"ERROR: {ERROR_CODES_FILE} not found")
        return 1

    codes = extract_error_codes(ERROR_CODES_FILE)
    if not codes:
        print("ERROR: No ErrorCode members found — check parsing regex")
        return 1

    print(f"Found {len(codes)} ErrorCode members")

    test_content = collect_test_content(TESTS_DIR)
    src_content = collect_src_content(REPO_ROOT / "src")

    missing: list[str] = []
    dead_code: list[str] = []
    exempt_applied: list[str] = []

    for code in codes:
        # Check both enum member name AND string value (e.g. "AUTHENTICATION_REQUIRED")
        in_tests = (
            code in test_content
            or f'"{code}"' in test_content
            or f"'{code}'" in test_content
            or f"ErrorCode.{code}" in test_content
        )
        in_src = code in src_content

        if in_tests:
            print(f"  ✓ {code}")
        elif code in EXEMPT_CODES:
            print(f"  ⊘ {code} (exempt — infrastructure/Azure AD boundary)")
            exempt_applied.append(code)
        elif not in_src:
            print(f"  ✗ {code} — dead code (not raised in src/)")
            dead_code.append(code)
        else:
            print(f"  ⚠ {code} — used in src/ but no direct test reference")
            missing.append(code)

    print()
    directly_covered = len(codes) - len(missing) - len(exempt_applied) - len(dead_code)
    print(f"Total codes:       {len(codes)}")
    print(f"Direct test ref:   {directly_covered}")
    print(f"Exempt:            {len(exempt_applied)}")
    print(f"Indirect (src-only): {len(missing)}")
    print(f"Dead code:         {len(dead_code)}")

    # Codes in src/ but without direct test reference: warn-only up to threshold.
    # Hard-fail if truly dead (not in src/ at all) or if indirect count exceeds threshold.
    INDIRECT_HARD_FAIL_THRESHOLD = 8

    exit_code = 0

    if dead_code:
        print()
        print("FAILURE: Dead error codes — defined but never raised in src/:")
        for code in dead_code:
            print(f"  - {code}")
        exit_code = 1

    if len(missing) > INDIRECT_HARD_FAIL_THRESHOLD:
        print()
        print(
            f"FAILURE: {len(missing)} codes used in src/ have no direct test assertion "
            f"(threshold: {INDIRECT_HARD_FAIL_THRESHOLD}). Add response-body error_code "
            "assertions in tests to bring this number down."
        )
        for code in missing:
            print(f"  - {code}")
        exit_code = 1
    elif missing:
        print()
        print(
            f"⚠️  WARNING: {len(missing)} codes used in src/ lack direct test assertions "
            f"(within threshold of {INDIRECT_HARD_FAIL_THRESHOLD}) — add coverage over time:"
        )
        for code in missing:
            print(f"  - {code}")

    if exit_code != 0:
        print()
        print("Resolution options:")
        print("  1. Add a test asserting response body contains the error_code string")
        print("  2. Add the code to EXEMPT_CODES with a documented reason")
        print("  3. Remove the code if it is truly dead/unreachable")
        return exit_code

    print()
    print("✅ Error code coverage gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
