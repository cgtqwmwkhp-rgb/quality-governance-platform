#!/usr/bin/env python3
"""
Evidence Validator for Branch Protection

This script validates that the required branch protection evidence artifacts exist.
It is designed to run in CI as a governance verification step.
"""

import sys
from pathlib import Path

# Required evidence artifacts
REQUIRED_ARTIFACTS = [
    "docs/evidence/branch_protection_rule.png",
    "docs/evidence/blocked_pr.png",
    "docs/evidence/direct_push_rejection.log",
]


def validate_evidence() -> int:
    """
    Validate that all required evidence artifacts exist.
    
    Returns:
        0 if all artifacts exist, 1 otherwise
    """
    repo_root = Path(__file__).parent.parent
    missing_artifacts = []
    
    print("=" * 60)
    print("Branch Protection Evidence Validator")
    print("=" * 60)
    
    for artifact_path in REQUIRED_ARTIFACTS:
        full_path = repo_root / artifact_path
        if full_path.exists():
            print(f"✅ FOUND: {artifact_path}")
        else:
            print(f"❌ MISSING: {artifact_path}")
            missing_artifacts.append(artifact_path)
    
    print("=" * 60)
    
    if missing_artifacts:
        print("\n❌ VALIDATION FAILED")
        print("\nMissing evidence artifacts:")
        for artifact in missing_artifacts:
            print(f"  - {artifact}")
        print("\nTo capture these artifacts, follow the instructions in:")
        print("  docs/BRANCH_PROTECTION_EVIDENCE_CHECKLIST.md")
        print("\nOr run the operator script:")
        print("  ./scripts/verify_branch_protection.sh")
        return 1
    else:
        print("\n✅ VALIDATION PASSED")
        print("All required evidence artifacts are present.")
        return 0


if __name__ == "__main__":
    sys.exit(validate_evidence())
