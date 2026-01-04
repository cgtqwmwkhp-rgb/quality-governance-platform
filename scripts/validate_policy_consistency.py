#!/usr/bin/env python3
"""
Policy Consistency Validator (Stage 1.3 Phase 2)

Validates that policy thresholds and values are consistent across all documentation,
scripts, and configuration files.

BLOCKING: This script must pass in CI to prevent policy drift and inconsistencies.

Policy Definitions:
- DRIFT_PREVENTION_DAYS: 30 days (max age for branch protection snapshot)
- QUARANTINE_MAX_DAYS: 90 days (max age for quarantined tests)

Exit Codes:
- 0: All policies are consistent
- 1: Policy inconsistencies detected
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Policy definitions (source of truth)
POLICIES = {
    "DRIFT_PREVENTION_DAYS": 30,
    "QUARANTINE_MAX_DAYS": 90,
}

# Files to check for each policy
# Only include files that exist and are part of implemented policies
POLICY_FILES = {
    "DRIFT_PREVENTION_DAYS": [
        "scripts/validate_branch_protection_drift.py",
        "docs/GOVERNANCE_DRIFT_PREVENTION.md",
    ],
    # QUARANTINE_MAX_DAYS: Not yet implemented in Stage 1.3
    # Will be validated when quarantine policy is implemented
}

# Patterns to match policy values in files
PATTERNS = {
    "DRIFT_PREVENTION_DAYS": [
        r"MAX_AGE_DAYS\s*=\s*(\d+)",  # Python constant
        r"(\d+)[\s-]*day[s]?\s+(?:freshness|drift|threshold)",  # Documentation
        r"(?:within|less than|under)\s+(\d+)\s+days?",  # Documentation
        r"<\s*(\d+)\s+days?",  # Documentation
    ],
    "QUARANTINE_MAX_DAYS": [
        r"MAX_QUARANTINE_DAYS\s*=\s*(\d+)",  # Python constant
        r"(\d+)[\s-]*day[s]?\s+(?:quarantine|threshold)",  # Documentation
        r"maximum\s+of\s+(\d+)\s+days?",  # Documentation
    ],
}


def extract_values(file_path: Path, patterns: List[str]) -> List[Tuple[int, str, int]]:
    """
    Extract all values matching the given patterns from a file.
    
    Returns:
        List of tuples: (line_number, matched_text, extracted_value)
    """
    if not file_path.exists():
        return []
    
    content = file_path.read_text()
    matches = []
    
    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern in patterns:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                try:
                    value = int(match.group(1))
                    matches.append((line_num, match.group(0), value))
                except (ValueError, IndexError):
                    continue
    
    return matches


def validate_policy(
    policy_name: str, expected_value: int, files: List[str]
) -> Tuple[bool, List[str]]:
    """
    Validate that a policy value is consistent across all specified files.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    repo_root = Path(__file__).parent.parent
    patterns = PATTERNS.get(policy_name, [])
    
    for file_path_str in files:
        file_path = repo_root / file_path_str
        
        if not file_path.exists():
            # Skip missing files - they may not be implemented yet
            print(f"  ⚠️  {file_path_str}: File not found (skipping)")
            continue
        
        matches = extract_values(file_path, patterns)
        
        if not matches:
            # This is a warning, not an error - file may not contain numeric policy value
            print(
                f"  ⚠️  {file_path_str}: No policy value found (expected {expected_value})"
            )
            continue
        
        # Check all matches
        inconsistent_values = [
            (line_num, text, value)
            for line_num, text, value in matches
            if value != expected_value
        ]
        
        if inconsistent_values:
            for line_num, text, value in inconsistent_values:
                errors.append(
                    f"  ❌ {file_path_str}:{line_num}: Found {value} (expected {expected_value})"
                    f"\n     Matched text: '{text}'"
                )
        else:
            # All values match
            print(f"  ✅ {file_path_str}: All values match ({expected_value})")
    
    return len(errors) == 0, errors


def main() -> int:
    """Main validation logic."""
    print("=" * 80)
    print("Policy Consistency Validation (Stage 1.3 Phase 2)")
    print("=" * 80)
    print()
    
    all_valid = True
    
    for policy_name, expected_value in POLICIES.items():
        print(f"Policy: {policy_name} = {expected_value}")
        print("-" * 80)
        
        files = POLICY_FILES.get(policy_name, [])
        if not files:
            print(f"  ⚠️  No files configured for validation")
            print()
            continue
        
        is_valid, errors = validate_policy(policy_name, expected_value, files)
        
        if not is_valid:
            all_valid = False
            for error in errors:
                print(error)
        
        print()
    
    print("=" * 80)
    if all_valid:
        print("✅ SUCCESS: All policies are consistent")
        print("=" * 80)
        return 0
    else:
        print("❌ FAILURE: Policy inconsistencies detected")
        print("=" * 80)
        print()
        print("Action Required:")
        print("- Update inconsistent values to match policy definitions")
        print("- Ensure all documentation reflects current policy values")
        print("- Re-run this script to verify fixes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
