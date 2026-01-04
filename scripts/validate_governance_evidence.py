#!/usr/bin/env python3
"""
Governance Evidence Validator

This script validates the presence of required evidence files for Stage 0.7 Gate 1.
It does NOT validate the content of the files; that must be done manually.

Exit codes:
- 0: All required evidence files are present
- 1: One or more required evidence files are missing
"""

import sys
from pathlib import Path

# Define the required evidence files
REQUIRED_EVIDENCE_FILES = [
    "docs/evidence/branch_protection_rule.png",
    "docs/evidence/blocked_pr.png",
    "docs/evidence/direct_push_rejection.log",
]


def main():
    """Validate the presence of required evidence files."""
    repo_root = Path(__file__).parent.parent
    missing_files = []

    print("=" * 80)
    print("GOVERNANCE EVIDENCE VALIDATOR (Stage 0.7 Gate 1)")
    print("=" * 80)
    print()

    for file_path in REQUIRED_EVIDENCE_FILES:
        full_path = repo_root / file_path
        if full_path.exists():
            print(f"✅ PRESENT: {file_path}")
        else:
            print(f"❌ MISSING: {file_path}")
            missing_files.append(file_path)

    print()
    print("=" * 80)

    if missing_files:
        print("VALIDATION FAILED: Missing evidence files")
        print("=" * 80)
        print()
        print("The following evidence files are required but not found:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        print()
        print("Please capture the missing evidence files according to:")
        print("  docs/BRANCH_PROTECTION_EVIDENCE_CHECKLIST.md")
        print()
        print("Note: This validator only checks file presence, not content.")
        print("Manual review of screenshots and logs is required.")
        sys.exit(1)
    else:
        print("VALIDATION PASSED: All required evidence files are present")
        print("=" * 80)
        print()
        print("Note: This validator only checks file presence, not content.")
        print("Manual review of screenshots and logs is required to ensure")
        print("they meet the requirements in:")
        print("  docs/BRANCH_PROTECTION_EVIDENCE_CHECKLIST.md")
        sys.exit(0)


if __name__ == "__main__":
    main()
