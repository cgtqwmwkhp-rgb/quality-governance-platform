#!/usr/bin/env python3
"""
Validate type-ignore comments to prevent silent drift.

Rules:
1. All type-ignore comments must be error-code-specific (e.g. # type: ignore[arg-type])
2. All type-ignore comments must include an issue ID tag (e.g. TYPE-IGNORE: GH-123)
3. Total count of type-ignores must not exceed the configured ceiling

Exit codes:
0 - All validations passed
1 - Validation failed
"""

import re
import sys
from pathlib import Path

# Configuration
MAX_TYPE_IGNORES = 5  # Current count: 4, allow small buffer
ISSUE_TAG_PATTERN = r"#\s*TYPE-IGNORE:\s*(GH-\d+|SQLALCHEMY-\d+|MYPY-\d+)"
SPECIFIC_IGNORE_PATTERN = r"#\s*type:\s*ignore\[[^\]]+\]"
GENERIC_IGNORE_PATTERN = r"#\s*type:\s*ignore(?!\[)"

def find_type_ignores(src_dir: Path) -> dict:
    """Find all type-ignore comments in Python files."""
    results = {
        "total": 0,
        "generic": [],
        "missing_issue_tag": [],
        "valid": [],
    }
    
    for py_file in src_dir.rglob("*.py"):
        if "venv" in str(py_file) or ".venv" in str(py_file):
            continue
            
        with open(py_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                # Check for generic type-ignore (no error code)
                if re.search(GENERIC_IGNORE_PATTERN, line):
                    results["generic"].append(f"{py_file}:{line_num}")
                    results["total"] += 1
                    continue
                
                # Check for specific type-ignore
                if re.search(SPECIFIC_IGNORE_PATTERN, line):
                    results["total"] += 1
                    
                    # Check if it has an issue tag
                    if not re.search(ISSUE_TAG_PATTERN, line):
                        results["missing_issue_tag"].append(f"{py_file}:{line_num}")
                    else:
                        results["valid"].append(f"{py_file}:{line_num}")
    
    return results

def main():
    src_dir = Path(__file__).parent.parent / "src"
    
    print("🔍 Validating type-ignore comments...")
    print(f"📊 Maximum allowed type-ignores: {MAX_TYPE_IGNORES}")
    print()
    
    results = find_type_ignores(src_dir)
    
    print(f"✅ Valid type-ignores (with issue tags): {len(results['valid'])}")
    for item in results["valid"]:
        print(f"   - {item}")
    print()
    
    errors = []
    
    # Check for generic type-ignores (no error code)
    if results["generic"]:
        errors.append(f"❌ Found {len(results['generic'])} generic type-ignore(s) without error codes:")
        for item in results["generic"]:
            errors.append(f"   - {item}")
        errors.append("   Fix: Use error-code-specific ignores (e.g. # type: ignore[arg-type])")
        errors.append("")
    
    # Check for type-ignores without issue tags
    if results["missing_issue_tag"]:
        errors.append(f"❌ Found {len(results['missing_issue_tag'])} type-ignore(s) without issue tags:")
        for item in results["missing_issue_tag"]:
            errors.append(f"   - {item}")
        errors.append("   Fix: Add issue tag (e.g. # type: ignore[arg-type]  # TYPE-IGNORE: GH-123)")
        errors.append("")
    
    # Check ceiling
    if results["total"] > MAX_TYPE_IGNORES:
        errors.append(f"❌ Type-ignore count ({results['total']}) exceeds ceiling ({MAX_TYPE_IGNORES})")
        errors.append(f"   Current: {results['total']}, Maximum: {MAX_TYPE_IGNORES}")
        errors.append("   Fix: Remove unnecessary type-ignores or update MAX_TYPE_IGNORES with approval")
        errors.append("")
    
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    
    print(f"✅ All type-ignore validations passed!")
    print(f"   Total type-ignores: {results['total']}/{MAX_TYPE_IGNORES}")
    sys.exit(0)

if __name__ == "__main__":
    main()
