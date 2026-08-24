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
from typing import List

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

    # Pattern: *custom* secrets used in contexts influenced by PR authors.
    # secrets.GITHUB_TOKEN is excluded — it is a built-in, scoped token
    # managed by GitHub and safe in standard pull_request workflows.
    unsafe_patterns = [
        (
            r"\$\{\{\s*secrets\.(?!GITHUB_TOKEN\b)\w+\s*\}\}.*\$\{\{\s*github\.event\.pull_request",
            "Custom secret used in same expression as pull_request data",
        ),
        (
            r"run:.*\$\{\{\s*secrets\.(?!GITHUB_TOKEN\b)\w+\s*\}\}.*\$\{\{\s*github\.event\.pull_request",
            "Custom secret and pull_request data in same run command",
        ),
    ]

    for pattern, description in unsafe_patterns:
        if re.search(pattern, content, re.DOTALL):
            errors.append(f"  ⚠️  {workflow_path.name}: Potentially unsafe secret usage")
            errors.append(f"     {description}")
            errors.append(f"     Review to ensure secrets are not exposed to PR context")

    return errors


def check_critical_gate_softening(workflow_path: Path) -> List[str]:
    """
    Enforce Stage 2.0 covenant: no soft-pass patterns in critical CI jobs.

    This check is intentionally conservative and targeted at known critical jobs.
    """
    errors = []
    content = workflow_path.read_text()

    # Only enforce this on the main CI workflow.
    if workflow_path.name != "ci.yml":
        return errors

    # Hard-fail if known critical jobs use continue-on-error.
    critical_jobs = ["integration-tests", "contract-tests", "security-scan", "smoke-tests"]
    for job in critical_jobs:
        job_block = re.search(rf"(?ms)^\s{{2}}{re.escape(job)}:\n(.*?)(?=^\s{{2}}\w[\w-]*:|\Z)", content)
        if job_block and re.search(r"^\s{8}continue-on-error:\s*true\s*$", job_block.group(1), re.MULTILINE):
            errors.append(
                f"  ❌ {workflow_path.name}: Critical job '{job}' uses continue-on-error=true (forbidden)"
            )

    # Block known placeholder pass-through pattern in contract tests.
    if re.search(r"pytest\s+tests/contract/.*\|\|\s*echo\s+\"Contract tests placeholder", content):
        errors.append(
            f"  ❌ {workflow_path.name}: Contract tests use placeholder pass-through (forbidden)"
        )

    return errors


# Every workflow that can set the container image on the production Web App. They must
# share one concurrency group so only one of them writes production at a time.
PRODUCTION_WRITERS = {
    "deploy-production.yml": False,
    "rollback-production.yml": True,
    "provision-production.yml": False,
}
PRODUCTION_LOCK_GROUP = "deploy-production"


def _top_level_concurrency(content: str) -> tuple:
    """
    Extract (group, cancel_in_progress) from a workflow's top-level concurrency block.

    Returns (None, None) when the workflow declares no top-level concurrency.
    """
    block = re.search(r"(?m)^concurrency:\s*\n((?:[ \t]+\S.*\n?)+)", content)
    if not block:
        return None, None

    body = block.group(1)
    group_match = re.search(r"(?m)^\s+group:\s*(.+?)\s*$", body)
    cancel_match = re.search(r"(?m)^\s+cancel-in-progress:\s*(true|false)\s*$", body)

    group = group_match.group(1) if group_match else None
    cancel = cancel_match.group(1) == "true" if cancel_match else None
    return group, cancel


def _group_joins_production_lock(group: str) -> bool:
    """
    True when a concurrency group actually joins the production lock.

    A substring test is not good enough: 'deploy-production-provision' contains
    'deploy-production' but is a different group, so a rename would pass unnoticed —
    exactly the silent drift this check exists to catch. Plain groups must match
    exactly. Expression groups (deploy-production.yml routes documentation-only runs
    elsewhere) must offer the bare group as one of their quoted branches.
    """
    group = group.strip()
    if "${{" in group:
        return re.search(rf"'{re.escape(PRODUCTION_LOCK_GROUP)}'", group) is not None
    return group.strip("\"'") == PRODUCTION_LOCK_GROUP


def check_production_writer_lock(repo_root: Path) -> List[str]:
    """
    Enforce that all production writers share one concurrency group.

    Drift here is silent: if one file's group is renamed and the others are not, no run
    fails and no annotation appears — the workflows simply deploy concurrently again and
    the last writer wins. Only the emergency rollback may preempt; a deploy must never
    cancel a write that is already in flight.
    """
    errors = []
    workflows_dir = repo_root / ".github" / "workflows"

    for filename, expect_cancel in PRODUCTION_WRITERS.items():
        path = workflows_dir / filename
        if not path.exists():
            errors.append(f"  ❌ {filename}: production writer is missing")
            errors.append(f"     If it was renamed, update PRODUCTION_WRITERS in {Path(__file__).name}")
            continue

        group, cancel = _top_level_concurrency(path.read_text())

        if group is None:
            errors.append(f"  ❌ {filename}: writes production but declares no concurrency group")
            errors.append(f"     Add a top-level `concurrency:` with group '{PRODUCTION_LOCK_GROUP}'")
        elif not _group_joins_production_lock(group):
            errors.append(f"  ❌ {filename}: concurrency group is not exactly '{PRODUCTION_LOCK_GROUP}'")
            errors.append(f"     Found: {group}")
            errors.append("     All production writers must share this group or the guard silently stops existing")

        if cancel is None:
            errors.append(f"  ❌ {filename}: concurrency block does not set cancel-in-progress")
        elif cancel != expect_cancel:
            errors.append(
                f"  ❌ {filename}: cancel-in-progress is {str(cancel).lower()}, expected {str(expect_cancel).lower()}"
            )
            if expect_cancel:
                errors.append("     The rollback must preempt: a pending run is cancelled by the next arrival,")
                errors.append("     so queueing means an emergency rollback can silently never run.")
            else:
                errors.append("     Only the emergency rollback may preempt; a deploy must never kill a live write.")

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
        errors.extend(check_critical_gate_softening(workflow_path))

        if errors:
            all_errors.extend(errors)
        else:
            print(f"  ✅ No security violations detected")

        print()

    print("Checking: production writer concurrency lock")
    lock_errors = check_production_writer_lock(repo_root)
    if lock_errors:
        all_errors.extend(lock_errors)
    else:
        print(f"  ✅ All {len(PRODUCTION_WRITERS)} production writers share group '{PRODUCTION_LOCK_GROUP}'")
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
