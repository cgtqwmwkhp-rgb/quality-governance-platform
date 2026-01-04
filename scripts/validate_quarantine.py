#!/usr/bin/env python3
"""
Quarantine Validation Script

This script enforces the TEST_QUARANTINE_POLICY by:
1. Scanning integration tests for @pytest.mark.skip decorators
2. Extracting skipped test names
3. Verifying each skipped test is documented in the policy
4. Failing if any undocumented skipped tests are found

This prevents silent expansion of the quarantine list.
"""

import re
import sys
from pathlib import Path


def extract_skipped_tests(test_dir: Path) -> set[str]:
    """Extract all test names that have @pytest.mark.skip decorator."""
    skipped_tests = set()
    
    for test_file in test_dir.rglob("test_*.py"):
        content = test_file.read_text()
        
        # Find all @pytest.mark.skip decorators followed by test definitions
        pattern = r'@pytest\.mark\.skip\([^)]*\)\s+(?:@[^\n]+\s+)*async\s+def\s+(test_\w+)'
        matches = re.finditer(pattern, content)
        
        for match in matches:
            test_name = match.group(1)
            skipped_tests.add(test_name)
    
    return skipped_tests


def extract_quarantined_tests(policy_file: Path) -> set[str]:
    """Extract test names documented in the quarantine policy."""
    if not policy_file.exists():
        return set()
    
    content = policy_file.read_text()
    quarantined_tests = set()
    
    # Find all test names in headers (### test_name)
    pattern = r'^###\s+(test_\w+)'
    matches = re.finditer(pattern, content, re.MULTILINE)
    
    for match in matches:
        test_name = match.group(1)
        quarantined_tests.add(test_name)
    
    return quarantined_tests


def main():
    """Main validation logic."""
    repo_root = Path(__file__).parent.parent
    test_dir = repo_root / "tests" / "integration"
    policy_file = repo_root / "docs" / "TEST_QUARANTINE_POLICY.md"
    
    print("🔍 Validating integration test quarantine policy...")
    print(f"   Test directory: {test_dir}")
    print(f"   Policy file: {policy_file}")
    print()
    
    # Extract skipped and quarantined tests
    skipped_tests = extract_skipped_tests(test_dir)
    quarantined_tests = extract_quarantined_tests(policy_file)
    
    print(f"✓ Found {len(skipped_tests)} skipped test(s)")
    print(f"✓ Found {len(quarantined_tests)} quarantined test(s) in policy")
    print()
    
    # Check for undocumented skipped tests
    undocumented = skipped_tests - quarantined_tests
    
    if undocumented:
        print("❌ QUARANTINE POLICY VIOLATION")
        print()
        print("The following tests are marked as skipped but are NOT documented")
        print("in docs/TEST_QUARANTINE_POLICY.md:")
        print()
        for test_name in sorted(undocumented):
            print(f"  - {test_name}")
        print()
        print("Action required:")
        print("1. Create a GitHub issue for the missing feature/bug")
        print("2. Add an entry to docs/TEST_QUARANTINE_POLICY.md with:")
        print("   - Test name, file, reason, issue link, owner, dates")
        print("3. Ensure the test has the correct skip marker format")
        print()
        sys.exit(1)
    
    # Check for orphaned policy entries
    orphaned = quarantined_tests - skipped_tests
    
    if orphaned:
        print("⚠️  WARNING: Orphaned quarantine entries")
        print()
        print("The following tests are documented in the policy but are NOT")
        print("marked as skipped in the test suite:")
        print()
        for test_name in sorted(orphaned):
            print(f"  - {test_name}")
        print()
        print("This may indicate the test was fixed or removed.")
        print("Consider removing these entries from the policy document.")
        print()
        # Don't fail on orphaned entries, just warn
    
    print("✅ Quarantine policy validation passed!")
    print()
    print("Summary:")
    print(f"  - {len(skipped_tests)} test(s) properly quarantined")
    print(f"  - 0 undocumented skipped tests")
    print(f"  - Merge gate remains strict for all non-quarantined tests")
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
