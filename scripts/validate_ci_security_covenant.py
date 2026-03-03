#!/usr/bin/env python3
"""
CI Security Covenant Validator (Stage 2.0 Phase 1)

Validates that CI workflows adhere to security best practices now that CI runs on all PRs.

BLOCKING: This script must pass in CI to prevent unsafe workflow configurations.

Security Checks:
- No use of pull_request_target (unless explicitly allowed via allowlist)
- No unsafe secret references in PR context

Exit Codes:
- 0: All security checks passed
- 1: Security violations detected
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Allowlist for pull_request_target (empty by default)
# To allow pull_request_target, create .github/workflows/pull_request_target_allowlist.txt
# with one workflow filename per line
ALLOWLIST_FILE = ".github/workflows/pull_request_target_allowlist.txt"


def load_allowlist(repo_root: Path) -> List[str]:
    """Load the allowlist of workflows permitted to use pull_request_target."""
    allowlist_path = repo_root / ALLOWLIST_FILE
    if not allowlist_path.exists():
        return []

    return [
        line.strip()
        for line in allowlist_path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def check_pull_request_target(workflow_path: Path, allowlist: List[str]) -> List[str]:
    """
    Check if a workflow uses pull_request_target.

    Returns:
        List of error messages (empty if no violations)
    """
    errors = []
    content = workflow_path.read_text()

    # Check for pull_request_target
    if re.search(r"^\s*pull_request_target\s*:", content, re.MULTILINE):
        if workflow_path.name not in allowlist:
            errors.append(f"  ❌ {workflow_path.name}: Uses pull_request_target without allowlist entry")
            errors.append(f"     Add to {ALLOWLIST_FILE} if this is intentional and documented")

    return errors


def check_unsafe_secret_usage(workflow_path: Path) -> List[str]:
    """
    Check for potentially unsafe secret usage patterns.

    Returns:
        List of error messages (empty if no violations)
    """
    errors = []
    content = workflow_path.read_text()

    # Pattern: secrets used in contexts that might be influenced by PR authors
    # This is a basic check; more sophisticated analysis may be needed
    unsafe_patterns = [
        (
            r"\$\{\{\s*secrets\.\w+\s*\}\}.*\$\{\{\s*github\.event\.pull_request",
            "Secret used in same expression as pull_request data",
        ),
        (
            r"run:.*\$\{\{\s*secrets\.\w+\s*\}\}.*\$\{\{\s*github\.event\.pull_request",
            "Secret and pull_request data in same run command",
        ),
    ]

    for pattern, description in unsafe_patterns:
        if re.search(pattern, content, re.DOTALL):
            errors.append(f"  ⚠️  {workflow_path.name}: Potentially unsafe secret usage")
            errors.append(f"     {description}")
            errors.append(f"     Review to ensure secrets are not exposed to PR context")

    return errors


def main() -> int:
    """Main validation logic."""
    print("=" * 80)
    print("CI Security Covenant Validation (Stage 2.0 Phase 1)")
    print("=" * 80)
    print()

    repo_root = Path(__file__).parent.parent
    workflows_dir = repo_root / ".github" / "workflows"

    if not workflows_dir.exists():
        print("❌ FAILURE: .github/workflows directory not found")
        return 1

    # Load allowlist
    allowlist = load_allowlist(repo_root)
    if allowlist:
        print(f"Allowlist loaded: {len(allowlist)} workflow(s) permitted to use pull_request_target")
        for workflow in allowlist:
            print(f"  - {workflow}")
        print()

    # Check all workflow files
    all_errors = []
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

    for workflow_path in workflow_files:
        print(f"Checking: {workflow_path.name}")

        errors = []
        errors.extend(check_pull_request_target(workflow_path, allowlist))
        errors.extend(check_unsafe_secret_usage(workflow_path))

        if errors:
            all_errors.extend(errors)
        else:
            print(f"  ✅ No security violations detected")

        print()

    print("=" * 80)
    if all_errors:
        print("❌ FAILURE: CI security violations detected")
        print("=" * 80)
        print()
        for error in all_errors:
            print(error)
        print()
        print("Action Required:")
        print("- Remove pull_request_target unless absolutely necessary")
        print("- If pull_request_target is required, document why and add to allowlist")
        print("- Ensure secrets are never exposed to PR context")
        return 1
    else:
        print("✅ SUCCESS: All CI security checks passed")
        print("=" * 80)
        return 0


if __name__ == "__main__":
    sys.exit(main())
