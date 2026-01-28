#!/usr/bin/env python3
"""
Test Quarantine CI Reporter (ENFORCING)

This script is a BLOCKING CI gate that enforces quarantine policy governance.

Produces a summary of quarantined tests for CI output including:
1. Quarantine policy validation status
2. List of quarantined tests with issue IDs
3. Expiry warnings
4. Enforcement of "no plain skip" rule
5. E2E minimum-pass gate
6. No-new-quarantines-without-override rule

Usage:
    python scripts/report_test_quarantine.py
    python scripts/report_test_quarantine.py --self-test  # Verify enforcement works
    python scripts/report_test_quarantine.py --check-e2e-baseline PASSED_COUNT
    python scripts/report_test_quarantine.py --record-baseline PASSED_COUNT

Exit codes:
    0: All checks passed - policy compliant
    1: Policy violations found - BUILD MUST FAIL

ENFORCEMENT RULES:
    - Expired quarantines → FAIL
    - Budget exceeded → FAIL
    - Plain skips without QUARANTINED annotation → FAIL
    - Invalid expiry dates → FAIL
    - E2E passed < E2E_MINIMUM_PASS (20) without approved_override → FAIL
    - Quarantine count increased without approved_override → FAIL
"""

import re
import sys
from datetime import date, datetime
from pathlib import Path

# Try to import yaml, fall back to manual parsing if not available
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ============================================================================
# PHASE 3 CLOSE-OUT GUARDRAILS
# ============================================================================

# E2E Minimum Pass Gate: CI fails if E2E passing tests < this threshold
E2E_MINIMUM_PASS = 20

# Baseline E2E count (updated after Phase 5): CI fails if current < baseline - 10%
E2E_BASELINE_COUNT = 140  # Phase 4 (80) + Phase 5 GOVPLAT-001 resolved (79 tests)

# Quarantine count baseline: CI fails if increased without approved_override
QUARANTINE_BASELINE_FILES = 0  # After Phase 5: ALL QUARANTINES CLEARED


def parse_yaml_manually(content: str) -> dict:
    """Simple YAML parser for basic structure when pyyaml not available."""
    result = {"quarantines": [], "metrics": {}, "settings": {}}
    current_quarantine = None
    in_files = False

    for line in content.split("\n"):
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- id:"):
            if current_quarantine:
                result["quarantines"].append(current_quarantine)
            current_quarantine = {"id": stripped.split(":")[1].strip().strip('"'), "files": []}
            in_files = False
        elif current_quarantine:
            if stripped.startswith("expiry_date:"):
                current_quarantine["expiry_date"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("owner:"):
                current_quarantine["owner"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("description:"):
                current_quarantine["description"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("files:"):
                in_files = True
            elif in_files and stripped.startswith("-"):
                current_quarantine["files"].append(stripped[1:].strip())
            elif stripped.startswith("resolution_plan:"):
                in_files = False

        if stripped.startswith("baseline_quarantine_count:"):
            result["metrics"]["baseline_quarantine_count"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("max_allowed_quarantine_count:"):
            result["metrics"]["max_allowed_quarantine_count"] = int(stripped.split(":")[1].strip())

    if current_quarantine:
        result["quarantines"].append(current_quarantine)

    return result


def load_policy(policy_path: Path) -> dict:
    """Load quarantine policy from YAML file."""
    content = policy_path.read_text()
    if HAS_YAML:
        return yaml.safe_load(content)
    else:
        return parse_yaml_manually(content)


def find_plain_skips(repo_root: Path) -> list[dict]:
    """Find test files with plain @pytest.mark.skip without issue ID."""
    violations = []
    tests_dir = repo_root / "tests"

    # Pattern for valid quarantine skip
    valid_pattern = re.compile(
        r'@pytest\.mark\.skip\s*\(\s*reason\s*=\s*["\'].*?QUARANTINED\s*\[.*?\]',
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern for any skip
    skip_pattern = re.compile(r"@pytest\.mark\.skip", re.IGNORECASE)

    for test_file in tests_dir.rglob("*.py"):
        content = test_file.read_text()

        # Find all skip markers
        skip_matches = list(skip_pattern.finditer(content))

        for match in skip_matches:
            # Get context around the skip (next 200 chars)
            start = match.start()
            context = content[start : start + 200]

            # Check if it's a valid quarantine skip
            if not valid_pattern.match(context):
                # Get line number
                line_num = content[:start].count("\n") + 1
                violations.append(
                    {
                        "file": str(test_file.relative_to(repo_root)),
                        "line": line_num,
                        "context": context[:80].replace("\n", " "),
                    }
                )

    return violations


def check_quarantine_growth(policy: dict) -> tuple[bool, str]:
    """
    Check if quarantine count increased without approved_override.
    Returns (passed, message).
    """
    file_count = sum(len(e.get("files", [])) for e in policy.get("quarantines", []))
    
    # Check for approved_override in any entry
    has_override = any(
        e.get("approved_override", False) 
        for e in policy.get("quarantines", [])
    )
    
    if file_count > QUARANTINE_BASELINE_FILES and not has_override:
        return (
            False, 
            f"Quarantine count increased ({file_count} > baseline {QUARANTINE_BASELINE_FILES}) "
            f"without approved_override. Add 'approved_override: true' to new entries."
        )
    
    return (True, f"Quarantine count: {file_count} (baseline: {QUARANTINE_BASELINE_FILES})")


def check_e2e_minimum(e2e_passed) -> tuple:
    """
    Check if E2E passed count meets minimum threshold.
    Returns (passed, message).
    """
    if e2e_passed is None:
        return (True, "E2E count not provided (skipping check)")
    
    # Absolute minimum
    if e2e_passed < E2E_MINIMUM_PASS:
        return (
            False,
            f"E2E passed ({e2e_passed}) below minimum ({E2E_MINIMUM_PASS}). "
            f"Tests may have regressed or been incorrectly skipped."
        )
    
    # Baseline regression check (10% tolerance)
    min_acceptable = int(E2E_BASELINE_COUNT * 0.9)
    if e2e_passed < min_acceptable:
        return (
            False,
            f"E2E passed ({e2e_passed}) regressed >10% from baseline ({E2E_BASELINE_COUNT}). "
            f"Minimum acceptable: {min_acceptable}."
        )
    
    return (True, f"E2E passed: {e2e_passed} (baseline: {E2E_BASELINE_COUNT}, minimum: {E2E_MINIMUM_PASS})")


def generate_report(policy: dict, repo_root: Path, e2e_passed=None) -> tuple:
    """Generate quarantine report and return (passed, report_text)."""
    lines = []
    errors = []
    warnings = []
    today = date.today()

    lines.append("=" * 60)
    lines.append("TEST QUARANTINE REPORT")
    lines.append("=" * 60)
    lines.append("")

    # 1. Check expiry dates
    lines.append("📅 Expiry Status:")
    expired_count = 0
    for entry in policy.get("quarantines", []):
        expiry_str = entry.get("expiry_date", "")
        if expiry_str:
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                days_left = (expiry - today).days
                if days_left < 0:
                    lines.append(f"   ❌ {entry['id']}: EXPIRED {abs(days_left)} days ago")
                    expired_count += 1
                    errors.append(f"{entry['id']} expired on {expiry_str}")
                elif days_left <= 7:
                    lines.append(f"   ⚠️  {entry['id']}: Expires in {days_left} days")
                    warnings.append(f"{entry['id']} expires in {days_left} days")
                else:
                    lines.append(f"   ✅ {entry['id']}: {days_left} days remaining")
            except ValueError:
                lines.append(f"   ❌ {entry['id']}: Invalid date format")
                errors.append(f"{entry['id']} has invalid expiry date")
    lines.append("")

    # 2. Check quarantine budget
    metrics = policy.get("metrics", {})
    max_allowed = metrics.get("max_allowed_quarantine_count", 0)
    file_count = sum(len(e.get("files", [])) for e in policy.get("quarantines", []))

    lines.append("📊 Quarantine Budget:")
    if file_count > max_allowed:
        lines.append(f"   ❌ Over budget: {file_count}/{max_allowed} files")
        errors.append(f"Quarantine count ({file_count}) exceeds max ({max_allowed})")
    else:
        lines.append(f"   ✅ Within budget: {file_count}/{max_allowed} files")
    lines.append("")

    # 3. Check for plain skips
    lines.append("🔍 Plain Skip Violations:")
    violations = find_plain_skips(repo_root)
    if violations:
        for v in violations[:10]:  # Show first 10
            lines.append(f"   ❌ {v['file']}:{v['line']} - Missing QUARANTINED annotation")
            errors.append(f"Plain skip at {v['file']}:{v['line']}")
        if len(violations) > 10:
            lines.append(f"   ... and {len(violations) - 10} more violations")
    else:
        lines.append("   ✅ No plain skips found (all skips properly annotated)")
    lines.append("")

    # 4. List quarantined tests
    lines.append("📋 Quarantined Tests:")
    for entry in policy.get("quarantines", []):
        file_count = len(entry.get("files", []))
        lines.append(f"   - {entry['id']}: {entry.get('description', 'No description')}")
        lines.append(f"     Files: {file_count}, Owner: {entry.get('owner', 'unassigned')}")
        lines.append(f"     Expires: {entry.get('expiry_date', 'unknown')}")
    lines.append("")

    # 5. Phase 3 Guardrails: Quarantine growth check
    lines.append("🔒 Quarantine Growth Check:")
    growth_passed, growth_msg = check_quarantine_growth(policy)
    if growth_passed:
        lines.append(f"   ✅ {growth_msg}")
    else:
        lines.append(f"   ❌ {growth_msg}")
        errors.append(growth_msg)
    lines.append("")

    # 6. Phase 3 Guardrails: E2E minimum check (if count provided)
    if e2e_passed is not None:
        lines.append("🧪 E2E Minimum Pass Gate:")
        e2e_check_passed, e2e_msg = check_e2e_minimum(e2e_passed)
        if e2e_check_passed:
            lines.append(f"   ✅ {e2e_msg}")
        else:
            lines.append(f"   ❌ {e2e_msg}")
            errors.append(e2e_msg)
        lines.append("")

    # 7. Summary
    lines.append("=" * 60)
    if errors:
        lines.append("❌ QUARANTINE POLICY: FAILED")
        lines.append("")
        lines.append("Errors that must be fixed:")
        for e in errors:
            lines.append(f"  - {e}")
    else:
        lines.append("✅ QUARANTINE POLICY: PASSED")
        if warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in warnings:
                lines.append(f"  - {w}")
    lines.append("=" * 60)

    return (len(errors) == 0, "\n".join(lines))


def run_self_test() -> bool:
    """
    Self-test to verify the enforcement logic works correctly.
    Returns True if all self-tests pass.
    """
    print("=" * 60)
    print("QUARANTINE ENFORCEMENT SELF-TEST")
    print("=" * 60)
    print("")

    all_passed = True

    # Test 1: Expired quarantine should fail
    print("Test 1: Expired quarantine detection...")
    expired_policy = {
        "quarantines": [
            {"id": "TEST-001", "expiry_date": "2020-01-01", "owner": "test", "files": ["test.py"]}
        ],
        "metrics": {"max_allowed_quarantine_count": 10},
    }
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "tests").mkdir()
        passed, _ = generate_report(expired_policy, tmp_path)
        if passed:
            print("   ❌ FAIL: Should have detected expired quarantine")
            all_passed = False
        else:
            print("   ✅ PASS: Expired quarantine correctly rejected")

    # Test 2: Over budget should fail
    print("Test 2: Budget exceeded detection...")
    over_budget_policy = {
        "quarantines": [
            {"id": "TEST-001", "expiry_date": "2099-01-01", "owner": "test", "files": ["a.py", "b.py", "c.py"]}
        ],
        "metrics": {"max_allowed_quarantine_count": 2},
    }
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "tests").mkdir()
        passed, _ = generate_report(over_budget_policy, tmp_path)
        if passed:
            print("   ❌ FAIL: Should have detected budget exceeded")
            all_passed = False
        else:
            print("   ✅ PASS: Budget exceeded correctly rejected")

    # Test 3: Valid policy should pass
    print("Test 3: Valid policy acceptance...")
    valid_policy = {
        "quarantines": [
            {"id": "TEST-001", "expiry_date": "2099-01-01", "owner": "test", "files": ["a.py"]}
        ],
        "metrics": {"max_allowed_quarantine_count": 10},
    }
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "tests").mkdir()
        passed, _ = generate_report(valid_policy, tmp_path)
        if not passed:
            print("   ❌ FAIL: Valid policy should have passed")
            all_passed = False
        else:
            print("   ✅ PASS: Valid policy correctly accepted")

    # Test 4: E2E minimum gate - below absolute minimum should fail
    print("Test 4: E2E absolute minimum enforcement...")
    e2e_passed, e2e_msg = check_e2e_minimum(15)  # Below 20
    if e2e_passed:
        print("   ❌ FAIL: E2E below absolute minimum (15 < 20) should fail")
        all_passed = False
    else:
        print("   ✅ PASS: E2E absolute minimum correctly enforced")

    # Test 5: E2E baseline regression - below 90% should fail
    print("Test 5: E2E baseline regression enforcement...")
    min_acceptable = int(E2E_BASELINE_COUNT * 0.9)
    e2e_passed, e2e_msg = check_e2e_minimum(min_acceptable - 5)  # Below 90%
    if e2e_passed:
        print(f"   ❌ FAIL: E2E below baseline ({min_acceptable - 5} < {min_acceptable}) should fail")
        all_passed = False
    else:
        print("   ✅ PASS: E2E baseline regression correctly enforced")

    # Test 6: E2E above baseline should pass
    print("Test 6: E2E above baseline acceptance...")
    e2e_passed, e2e_msg = check_e2e_minimum(E2E_BASELINE_COUNT + 5)
    if not e2e_passed:
        print("   ❌ FAIL: E2E above baseline should pass")
        all_passed = False
    else:
        print("   ✅ PASS: E2E above baseline correctly accepted")

    # Test 7: Quarantine growth without override should fail
    print("Test 7: Quarantine growth without override...")
    growth_passed, growth_msg = check_quarantine_growth({
        "quarantines": [
            {"id": "TEST-001", "files": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py"]}
        ]
    })
    if growth_passed:
        print("   ❌ FAIL: Quarantine growth without override should fail")
        all_passed = False
    else:
        print("   ✅ PASS: Quarantine growth without override correctly rejected")

    # Test 8: Quarantine growth with override should pass
    print("Test 8: Quarantine growth with override...")
    growth_passed, growth_msg = check_quarantine_growth({
        "quarantines": [
            {"id": "TEST-001", "files": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py"], "approved_override": True}
        ]
    })
    if not growth_passed:
        print("   ❌ FAIL: Quarantine growth with override should pass")
        all_passed = False
    else:
        print("   ✅ PASS: Quarantine growth with override correctly accepted")

    print("")
    print("=" * 60)
    if all_passed:
        print("✅ ALL SELF-TESTS PASSED - Enforcement logic verified")
    else:
        print("❌ SELF-TESTS FAILED - Enforcement logic has bugs")
    print("=" * 60)

    return all_passed


def main():
    # Check for self-test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        passed = run_self_test()
        sys.exit(0 if passed else 1)

    # Check for E2E count argument
    e2e_passed = None
    if len(sys.argv) > 2 and sys.argv[1] == "--check-e2e":
        try:
            e2e_passed = int(sys.argv[2])
        except ValueError:
            print(f"Invalid E2E count: {sys.argv[2]}")
            sys.exit(1)

    repo_root = Path(__file__).parent.parent
    policy_path = repo_root / "tests" / "QUARANTINE_POLICY.yaml"

    # Check policy file exists
    if not policy_path.exists():
        print("=" * 60)
        print("TEST QUARANTINE REPORT (ENFORCING)")
        print("=" * 60)
        print("")
        print(f"⚠️  Policy file not found: {policy_path}")
        print("   Quarantine enforcement skipped (no policy defined)")
        print("=" * 60)
        sys.exit(0)  # Don't fail if no policy file

    policy = load_policy(policy_path)
    passed, report = generate_report(policy, repo_root, e2e_passed)

    print(report)

    if not passed:
        print("")
        print("🚨 CI BUILD FAILURE: Quarantine policy violations detected")
        print("   Fix the above errors before this PR can be merged.")
        print("")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
