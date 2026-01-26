#!/usr/bin/env python3
"""
Quarantine Policy Validation Script

Enforces quarantine governance by:
1. Validating QUARANTINE_POLICY.yaml structure
2. Checking expiry dates (fails if any are past)
3. Validating quarantine count against baseline (prevents growth)
4. Verifying all quarantined files exist

Exit codes:
- 0: All checks passed
- 1: Validation failed
"""

import sys
from datetime import date, datetime
from pathlib import Path

# Try to import yaml, fall back to manual parsing if not available
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_yaml_manually(content: str) -> dict:
    """Simple YAML parser for basic structure when pyyaml not available."""
    result = {"quarantines": [], "metrics": {}, "settings": {}}
    current_quarantine = None
    in_files = False

    for line in content.split("\n"):
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        # Parse quarantine entries
        if stripped.startswith("- id:"):
            if current_quarantine:
                result["quarantines"].append(current_quarantine)
            current_quarantine = {"id": stripped.split(":")[1].strip().strip('"')}
            in_files = False
        elif current_quarantine:
            if stripped.startswith("expiry_date:"):
                current_quarantine["expiry_date"] = stripped.split(":")[1].strip().strip('"')
            elif stripped.startswith("owner:"):
                current_quarantine["owner"] = stripped.split(":")[1].strip().strip('"')
            elif stripped.startswith("marker:"):
                current_quarantine["marker"] = stripped.split(":")[1].strip().strip('"')
            elif stripped.startswith("files:"):
                current_quarantine["files"] = []
                in_files = True
            elif in_files and stripped.startswith("-"):
                current_quarantine["files"].append(stripped[1:].strip())
            elif stripped.startswith("resolution_plan:"):
                in_files = False

        # Parse metrics
        if stripped.startswith("baseline_quarantine_count:"):
            result["metrics"]["baseline_quarantine_count"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("max_allowed_quarantine_count:"):
            result["metrics"]["max_allowed_quarantine_count"] = int(stripped.split(":")[1].strip())

        # Parse settings
        if stripped.startswith("enforce_expiry:"):
            result["settings"]["enforce_expiry"] = stripped.split(":")[1].strip().lower() == "true"
        elif stripped.startswith("block_on_expiry:"):
            result["settings"]["block_on_expiry"] = stripped.split(":")[1].strip().lower() == "true"

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


def validate_expiry_dates(policy: dict) -> list[str]:
    """Check if any quarantine entries have expired."""
    errors = []
    today = date.today()

    for entry in policy.get("quarantines", []):
        expiry_str = entry.get("expiry_date", "")
        if not expiry_str:
            errors.append(f"{entry.get('id', 'unknown')}: Missing expiry_date")
            continue

        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            if today > expiry:
                errors.append(f"{entry['id']}: EXPIRED on {expiry_str} " f"({(today - expiry).days} days ago)")
        except ValueError as e:
            errors.append(f"{entry.get('id', 'unknown')}: Invalid date format: {e}")

    return errors


def validate_quarantine_count(policy: dict, repo_root: Path) -> list[str]:
    """Validate quarantine count against baseline."""
    errors = []
    metrics = policy.get("metrics", {})

    max_allowed = metrics.get("max_allowed_quarantine_count", 0)

    # Count actual quarantined files
    actual_count = 0
    for entry in policy.get("quarantines", []):
        actual_count += len(entry.get("files", []))

    if actual_count > max_allowed:
        errors.append(
            f"Quarantine count ({actual_count}) exceeds max allowed ({max_allowed}). "
            "Update QUARANTINE_POLICY.yaml with justification to increase limit."
        )

    return errors


def validate_required_fields(policy: dict) -> list[str]:
    """Validate all quarantine entries have required fields."""
    errors = []
    required_fields = ["id", "expiry_date", "owner", "reason", "marker"]

    for entry in policy.get("quarantines", []):
        entry_id = entry.get("id", "unknown")
        for field in required_fields:
            if field not in entry or not entry[field]:
                errors.append(f"{entry_id}: Missing required field '{field}'")

    return errors


def validate_files_exist(policy: dict, repo_root: Path) -> list[str]:
    """Validate all quarantined files exist."""
    warnings = []

    for entry in policy.get("quarantines", []):
        entry_id = entry.get("id", "unknown")
        for file_path in entry.get("files", []):
            full_path = repo_root / file_path
            if not full_path.exists():
                warnings.append(f"{entry_id}: File not found: {file_path}")

    return warnings


def main():
    """Main validation logic."""
    repo_root = Path(__file__).parent.parent
    policy_path = repo_root / "tests" / "QUARANTINE_POLICY.yaml"

    print("=" * 60)
    print("QUARANTINE POLICY VALIDATION")
    print("=" * 60)
    print()

    # Check policy file exists
    if not policy_path.exists():
        print(f"❌ Policy file not found: {policy_path}")
        sys.exit(1)

    print(f"📋 Loading policy from: {policy_path}")
    policy = load_policy(policy_path)

    quarantine_count = len(policy.get("quarantines", []))
    file_count = sum(len(e.get("files", [])) for e in policy.get("quarantines", []))

    print(f"   Found {quarantine_count} quarantine entries ({file_count} files)")
    print()

    all_errors = []
    all_warnings = []

    # 1. Validate required fields
    print("🔍 Checking required fields...")
    errors = validate_required_fields(policy)
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   ❌ {e}")
    else:
        print("   ✅ All required fields present")
    print()

    # 2. Validate expiry dates
    print("🔍 Checking expiry dates...")
    errors = validate_expiry_dates(policy)
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   ❌ {e}")
    else:
        print("   ✅ No expired quarantines")
    print()

    # 3. Validate quarantine count
    print("🔍 Checking quarantine count budget...")
    errors = validate_quarantine_count(policy, repo_root)
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   ❌ {e}")
    else:
        max_allowed = policy.get("metrics", {}).get("max_allowed_quarantine_count", 0)
        print(f"   ✅ Within budget ({file_count}/{max_allowed} files)")
    print()

    # 4. Validate files exist (warning only)
    print("🔍 Checking quarantined files exist...")
    warnings = validate_files_exist(policy, repo_root)
    if warnings:
        all_warnings.extend(warnings)
        for w in warnings:
            print(f"   ⚠️  {w}")
    else:
        print("   ✅ All quarantined files found")
    print()

    # Summary
    print("=" * 60)
    if all_errors:
        print("❌ QUARANTINE POLICY VALIDATION FAILED")
        print()
        print("Errors that must be fixed:")
        for e in all_errors:
            print(f"  - {e}")
        print()
        print("Actions required:")
        print("  1. For expired quarantines: Fix the tests or request extension")
        print("  2. For budget exceeded: Update max_allowed_quarantine_count with justification")
        print("  3. For missing fields: Add required metadata to entries")
        sys.exit(1)
    else:
        print("✅ QUARANTINE POLICY VALIDATION PASSED")
        if all_warnings:
            print()
            print("Warnings (non-blocking):")
            for w in all_warnings:
                print(f"  - {w}")

    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
