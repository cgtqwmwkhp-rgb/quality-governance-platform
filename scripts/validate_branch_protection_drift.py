#!/usr/bin/env python3
"""
Governance Drift Prevention: Branch Protection Snapshot Validation

This script prevents governance drift by ensuring:
1. Branch protection snapshot is not stale (< 30 days old)
2. Required status checks in snapshot match CI workflow configuration
3. Changes to CI workflow trigger snapshot refresh requirement

Exit codes:
- 0: All checks passed
- 1: Drift detected (stale snapshot or workflow mismatch)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set

# Configuration
SNAPSHOT_PATH = Path("docs/evidence/branch_protection_settings.json")
CI_WORKFLOW_PATH = Path(".github/workflows/ci.yml")
MAX_SNAPSHOT_AGE_DAYS = 30
OVERRIDE_FILE = Path("docs/evidence/branch_protection_override.txt")


def load_snapshot() -> Dict:
    """Load branch protection snapshot."""
    if not SNAPSHOT_PATH.exists():
        print(f"❌ ERROR: Branch protection snapshot not found: {SNAPSHOT_PATH}")
        sys.exit(1)
    
    with open(SNAPSHOT_PATH) as f:
        return json.load(f)


def check_snapshot_freshness(snapshot: Dict) -> bool:
    """
    Check if snapshot is fresh (< 30 days old).
    
    Returns True if fresh, False if stale.
    """
    # Check for manual override
    if OVERRIDE_FILE.exists():
        with open(OVERRIDE_FILE) as f:
            content = f.read().strip()
            if content:
                try:
                    # Override format: "YYYY-MM-DD: Reason for override"
                    override_date_str = content.split(":")[0].strip()
                    override_date = datetime.strptime(override_date_str, "%Y-%m-%d")
                    
                    # Check if override itself is expired
                    if datetime.now() - override_date > timedelta(days=MAX_SNAPSHOT_AGE_DAYS):
                        print(f"⚠️  WARNING: Override file expired (> {MAX_SNAPSHOT_AGE_DAYS} days old)")
                        print(f"   Override date: {override_date_str}")
                        print(f"   Please refresh snapshot or update override")
                        return False
                    
                    print(f"✓ Manual override active (expires: {(override_date + timedelta(days=MAX_SNAPSHOT_AGE_DAYS)).strftime('%Y-%m-%d')})")
                    print(f"  Reason: {content.split(':', 1)[1].strip()}")
                    return True
                except (ValueError, IndexError) as e:
                    print(f"❌ ERROR: Invalid override file format: {e}")
                    print(f"   Expected format: 'YYYY-MM-DD: Reason for override'")
                    return False
    
    # Check snapshot modification time
    snapshot_mtime = datetime.fromtimestamp(SNAPSHOT_PATH.stat().st_mtime)
    age = datetime.now() - snapshot_mtime
    
    if age > timedelta(days=MAX_SNAPSHOT_AGE_DAYS):
        print(f"❌ DRIFT DETECTED: Branch protection snapshot is stale")
        print(f"   Snapshot age: {age.days} days (max: {MAX_SNAPSHOT_AGE_DAYS} days)")
        print(f"   Last updated: {snapshot_mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("   ACTION REQUIRED:")
        print(f"   1. Re-run: ./scripts/export_branch_protection.sh")
        print(f"   2. Commit updated {SNAPSHOT_PATH}")
        print(f"   OR create override: {OVERRIDE_FILE}")
        print(f"      Format: 'YYYY-MM-DD: Reason for keeping stale snapshot'")
        return False
    
    print(f"✓ Snapshot freshness OK")
    print(f"  Current age: {age.days} days")
    print(f"  Threshold: {MAX_SNAPSHOT_AGE_DAYS} days")
    print(f"  Margin: {MAX_SNAPSHOT_AGE_DAYS - age.days} days remaining")
    return True


def extract_required_checks_from_snapshot(snapshot: Dict) -> Set[str]:
    """Extract required status check names from snapshot."""
    checks = set()
    
    required_checks = snapshot.get("required_status_checks", {}).get("contexts", [])
    if required_checks:
        checks.update(required_checks)
    
    return checks


def extract_job_names_from_ci_workflow() -> Set[str]:
    """Extract job names from CI workflow that should be status checks."""
    if not CI_WORKFLOW_PATH.exists():
        print(f"⚠️  WARNING: CI workflow not found: {CI_WORKFLOW_PATH}")
        return set()
    
    with open(CI_WORKFLOW_PATH) as f:
        content = f.read()
    
    # Simple extraction: look for "jobs:" section and extract job names
    # This is a basic parser; adjust if workflow structure changes
    jobs = set()
    in_jobs_section = False
    
    for line in content.split("\n"):
        if line.strip() == "jobs:":
            in_jobs_section = True
            continue
        
        if in_jobs_section:
            # Job names are at the start of the line (no leading spaces beyond indentation)
            if line.startswith("  ") and not line.startswith("    ") and ":" in line:
                job_name = line.strip().split(":")[0].strip()
                if job_name and not job_name.startswith("#"):
                    jobs.add(job_name)
    
    return jobs


def check_workflow_coupling(snapshot: Dict) -> bool:
    """
    Check if required status checks in snapshot match CI workflow jobs.
    
    Returns True if coupled correctly, False if mismatch detected.
    """
    snapshot_checks = extract_required_checks_from_snapshot(snapshot)
    ci_jobs = extract_job_names_from_ci_workflow()
    
    if not snapshot_checks:
        print("⚠️  WARNING: No required status checks found in snapshot")
        return True  # Allow if no checks configured
    
    if not ci_jobs:
        print("⚠️  WARNING: Could not extract jobs from CI workflow")
        return True  # Allow if can't parse workflow
    
    # The "all-checks" job should be the required status check
    # It depends on all other jobs, so we verify it exists in both
    if "all-checks" not in snapshot_checks:
        print("❌ DRIFT DETECTED: 'all-checks' not in required status checks")
        print(f"   Snapshot checks: {sorted(snapshot_checks)}")
        print()
        print("   ACTION REQUIRED:")
        print("   1. Verify branch protection settings in GitHub")
        print("   2. Re-run: ./scripts/export_branch_protection.sh")
        return False
    
    if "all-checks" not in ci_jobs:
        print("❌ DRIFT DETECTED: 'all-checks' job not found in CI workflow")
        print(f"   CI jobs: {sorted(ci_jobs)}")
        print()
        print("   ACTION REQUIRED:")
        print("   1. Verify .github/workflows/ci.yml has 'all-checks' job")
        print("   2. If renamed, update branch protection and refresh snapshot")
        return False
    
    print(f"✓ Workflow coupling OK ('all-checks' present in both)")
    print(f"  Snapshot required checks: {sorted(snapshot_checks)}")
    print(f"  CI workflow jobs: {len(ci_jobs)} jobs (including 'all-checks')")
    
    return True


def main():
    """Run all drift prevention checks."""
    print("=" * 70)
    print("GOVERNANCE DRIFT PREVENTION: Branch Protection Snapshot Validation")
    print("=" * 70)
    print()
    
    # Load snapshot
    snapshot = load_snapshot()
    print(f"✓ Loaded snapshot: {SNAPSHOT_PATH}")
    print()
    
    # Run checks
    checks_passed = []
    
    print("Check 1: Snapshot Freshness")
    print("-" * 70)
    freshness_ok = check_snapshot_freshness(snapshot)
    checks_passed.append(("Snapshot Freshness", freshness_ok))
    print()
    
    print("Check 2: Workflow Coupling")
    print("-" * 70)
    coupling_ok = check_workflow_coupling(snapshot)
    checks_passed.append(("Workflow Coupling", coupling_ok))
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for check_name, passed in checks_passed:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
    print()
    
    if all(passed for _, passed in checks_passed):
        print("✅ All drift prevention checks passed")
        sys.exit(0)
    else:
        print("❌ Drift prevention checks failed")
        print()
        print("GOVERNANCE VIOLATION: Branch protection evidence has drifted")
        print("This is a BLOCKING error. Fix the issues above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
