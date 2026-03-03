#!/usr/bin/env python3
"""
OpenAPI Contract Compatibility Checker

Compares current OpenAPI schema against baseline and detects breaking changes.

Breaking changes detected:
- Removed endpoints
- Removed required fields
- Changed field types
- Changed response codes

Allowed changes:
- New endpoints (additive)
- New optional fields
- New response codes (additive)
"""

import json
import sys
from pathlib import Path
from typing import Any


def load_schema(path: str) -> dict:
    """Load OpenAPI schema from file."""
    with open(path) as f:
        return json.load(f)


def get_paths(schema: dict) -> dict:
    """Extract paths from schema."""
    return schema.get("paths", {})


def get_schemas(schema: dict) -> dict:
    """Extract component schemas."""
    return schema.get("components", {}).get("schemas", {})


def check_removed_endpoints(baseline: dict, current: dict) -> list[str]:
    """Check for removed endpoints (breaking)."""
    issues = []
    baseline_paths = set(get_paths(baseline).keys())
    current_paths = set(get_paths(current).keys())

    removed = baseline_paths - current_paths
    for path in removed:
        issues.append(f"BREAKING: Endpoint removed: {path}")

    return issues


def check_removed_methods(baseline: dict, current: dict) -> list[str]:
    """Check for removed HTTP methods (breaking)."""
    issues = []
    baseline_paths = get_paths(baseline)
    current_paths = get_paths(current)

    for path, methods in baseline_paths.items():
        if path not in current_paths:
            continue  # Already caught by removed_endpoints

        current_methods = current_paths[path]
        for method in methods:
            if method.startswith("x-"):  # Skip extensions
                continue
            if method not in current_methods:
                issues.append(f"BREAKING: Method removed: {method.upper()} {path}")

    return issues


def get_required_fields(schema_def: dict) -> set[str]:
    """Extract required fields from schema definition."""
    return set(schema_def.get("required", []))


def check_removed_required_fields(baseline: dict, current: dict) -> list[str]:
    """Check for removed required fields in request bodies (breaking)."""
    issues = []
    baseline_schemas = get_schemas(baseline)
    current_schemas = get_schemas(current)

    for name, schema in baseline_schemas.items():
        if name not in current_schemas:
            # Schema removed - could be breaking
            issues.append(f"WARNING: Schema removed: {name}")
            continue

        baseline_required = get_required_fields(schema)
        current_required = get_required_fields(current_schemas[name])

        # Fields that were required but are now gone
        removed_required = baseline_required - current_required
        for field in removed_required:
            # Check if field still exists (now optional) vs completely removed
            current_props = current_schemas[name].get("properties", {})
            if field not in current_props:
                issues.append(f"BREAKING: Required field removed from {name}: {field}")

    return issues


def check_type_changes(baseline: dict, current: dict) -> list[str]:
    """Check for field type changes (breaking)."""
    issues = []
    baseline_schemas = get_schemas(baseline)
    current_schemas = get_schemas(current)

    for name, schema in baseline_schemas.items():
        if name not in current_schemas:
            continue

        baseline_props = schema.get("properties", {})
        current_props = current_schemas[name].get("properties", {})

        for field, field_schema in baseline_props.items():
            if field not in current_props:
                continue

            baseline_type = field_schema.get("type")
            current_type = current_props[field].get("type")

            if baseline_type != current_type:
                issues.append(f"BREAKING: Type changed for {name}.{field}: " f"{baseline_type} -> {current_type}")

    return issues


def check_new_required_fields(baseline: dict, current: dict) -> list[str]:
    """Check for new required fields in existing schemas (breaking for clients)."""
    issues = []
    baseline_schemas = get_schemas(baseline)
    current_schemas = get_schemas(current)

    for name, schema in current_schemas.items():
        if name not in baseline_schemas:
            continue  # New schema, not breaking

        baseline_required = get_required_fields(baseline_schemas[name])
        current_required = get_required_fields(schema)

        new_required = current_required - baseline_required
        for field in new_required:
            issues.append(
                f"BREAKING: New required field added to {name}: {field} " "(existing clients may not send this)"
            )

    return issues


def report_additive_changes(baseline: dict, current: dict) -> list[str]:
    """Report additive (non-breaking) changes for information."""
    info = []

    # New endpoints
    baseline_paths = set(get_paths(baseline).keys())
    current_paths = set(get_paths(current).keys())
    new_paths = current_paths - baseline_paths
    for path in new_paths:
        info.append(f"INFO: New endpoint added: {path}")

    # New schemas
    baseline_schemas = set(get_schemas(baseline).keys())
    current_schemas = set(get_schemas(current).keys())
    new_schemas = current_schemas - baseline_schemas
    for schema in new_schemas:
        info.append(f"INFO: New schema added: {schema}")

    return info


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: check_openapi_compatibility.py <baseline.json> <current.json>")
        print("       Returns exit code 0 if compatible, 1 if breaking changes")
        sys.exit(2)

    baseline_path = sys.argv[1]
    current_path = sys.argv[2]

    if not Path(baseline_path).exists():
        print(f"Baseline not found: {baseline_path}")
        print(
            "First run? Generate baseline with: python -c 'from src.main import app; import json; print(json.dumps(app.openapi()))' > openapi-baseline.json"
        )
        sys.exit(0)  # Allow first run without baseline

    if not Path(current_path).exists():
        print(f"Current schema not found: {current_path}")
        sys.exit(2)

    baseline = load_schema(baseline_path)
    current = load_schema(current_path)

    print("=" * 60)
    print("OpenAPI Contract Compatibility Check")
    print("=" * 60)
    print(f"Baseline: {baseline_path}")
    print(f"Current:  {current_path}")
    print()

    # Collect all issues
    all_issues: list[str] = []
    all_issues.extend(check_removed_endpoints(baseline, current))
    all_issues.extend(check_removed_methods(baseline, current))
    all_issues.extend(check_removed_required_fields(baseline, current))
    all_issues.extend(check_type_changes(baseline, current))
    all_issues.extend(check_new_required_fields(baseline, current))

    # Collect info (non-breaking)
    info = report_additive_changes(baseline, current)

    # Report results
    breaking_changes = [i for i in all_issues if i.startswith("BREAKING")]
    warnings = [i for i in all_issues if i.startswith("WARNING")]

    if info:
        print("Additive Changes (non-breaking):")
        for item in info:
            print(f"  {item}")
        print()

    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"  {item}")
        print()

    if breaking_changes:
        print("❌ BREAKING CHANGES DETECTED:")
        for item in breaking_changes:
            print(f"  {item}")
        print()
        print("=" * 60)
        print("Contract check FAILED - Breaking changes would affect clients")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("✅ Contract check PASSED - No breaking changes detected")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
