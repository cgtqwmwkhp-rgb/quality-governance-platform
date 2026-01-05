#!/usr/bin/env python3
"""
Acceptance Pack Validator

Validates that Stage acceptance packs contain required fields:
- CI run URL
- Final commit SHA
- Touched files table
- Rollback notes
"""

import re
import sys
from pathlib import Path


def validate_acceptance_pack(path: Path) -> list[str]:
    """Validate acceptance pack contains required fields."""
    errors = []

    if not path.exists():
        return [f"Acceptance pack not found: {path}"]

    content = path.read_text()

    # Check for CI run URL (GitHub Actions URL pattern)
    if not re.search(r"https://github\.com/[^/]+/[^/]+/actions/runs/\d+", content):
        errors.append("Missing CI run URL (GitHub Actions URL)")

    # Check for commit SHA (40-character hex string)
    if not re.search(r"\b[0-9a-f]{7,40}\b", content):
        errors.append("Missing commit SHA")

    # Check for touched files table (should have file paths and line counts)
    if not re.search(r"\|\s*File\s*\|", content, re.IGNORECASE):
        errors.append("Missing touched files table")

    # Check for rollback notes section
    if not re.search(r"rollback", content, re.IGNORECASE):
        errors.append("Missing rollback notes")

    # Check for phase summaries
    if not re.search(r"phase\s+\d+", content, re.IGNORECASE):
        errors.append("Missing phase summaries")

    return errors


def main():
    """Run acceptance pack validation."""
    # Look for acceptance pack in docs/evidence/
    evidence_dir = Path("docs/evidence")

    if not evidence_dir.exists():
        print("❌ docs/evidence/ directory not found")
        sys.exit(1)

    # Find all acceptance pack files
    acceptance_packs = list(evidence_dir.glob("STAGE*_ACCEPTANCE_PACK.md"))

    if not acceptance_packs:
        print("⚠️  No acceptance packs found in docs/evidence/")
        print("   This is OK for non-stage PRs")
        sys.exit(0)

    print(f"🔍 Validating {len(acceptance_packs)} acceptance pack(s)...")

    all_errors = []
    for pack in acceptance_packs:
        errors = validate_acceptance_pack(pack)
        if errors:
            all_errors.append((pack.name, errors))

    if all_errors:
        print(f"\n❌ Found validation errors:\n")
        for pack_name, errors in all_errors:
            print(f"  {pack_name}:")
            for error in errors:
                print(f"    - {error}")
        sys.exit(1)

    print(f"✅ All acceptance packs validated successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
