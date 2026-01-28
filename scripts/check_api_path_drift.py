#!/usr/bin/env python3
"""
API Path Drift Prevention Script

Scans test files to ensure consistent API path usage:
- Rejects bare "/api/" usage (without version)
- Requires "/api/v1/" for all API endpoints
- Allows explicit allowlist for exceptions

Exit codes:
  0 - No drift detected
  1 - Drift detected (violations found)
  2 - Configuration error
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


@dataclass
class Violation:
    """Represents a path drift violation."""
    file: str
    line: int
    column: int
    pattern: str
    context: str
    remediation: str


# Patterns that indicate drift (bare /api/ without version)
DRIFT_PATTERNS = [
    # Matches /api/ followed by anything except 'v' (version indicator)
    (r'["\']\/api\/(?!v\d+)[a-zA-Z]', "Bare /api/ without version prefix"),
    # Matches /api/ at end of string or followed by quote
    (r'["\']\/api\/["\']', "Bare /api/ endpoint"),
    # Matches /api/ followed by path but not version
    (r'["\']\/api\/(?!v\d+\/)[a-zA-Z_]+\/', "API path without version"),
]

# Allowed patterns (exceptions)
ALLOWED_PATTERNS = [
    r'\/api\/v\d+\/',  # Versioned API paths
    r'\/api\/v\d+$',   # Versioned API root
    r'\/healthz',      # Health endpoint
    r'\/readyz',       # Readiness endpoint
]

# Default allowlist file location
ALLOWLIST_FILE = "docs/contracts/api_path_allowlist.json"


def load_allowlist(allowlist_path: Optional[Path]) -> Set[str]:
    """Load allowlisted patterns from JSON file."""
    if allowlist_path is None:
        return set()
    
    if not allowlist_path.exists():
        return set()
    
    try:
        with open(allowlist_path, 'r') as f:
            data = json.load(f)
            return set(data.get('allowed_paths', []))
    except (json.JSONDecodeError, KeyError):
        print(f"⚠️  Warning: Could not parse allowlist file: {allowlist_path}")
        return set()


def is_allowlisted(line: str, allowlist: Set[str]) -> bool:
    """Check if a line matches an allowed pattern or is in allowlist."""
    # Check standard allowed patterns
    for pattern in ALLOWED_PATTERNS:
        if re.search(pattern, line):
            return True
    
    # Check custom allowlist
    for allowed in allowlist:
        if allowed in line:
            return True
    
    return False


def scan_file(filepath: Path, allowlist: Set[str]) -> List[Violation]:
    """Scan a single file for API path drift violations."""
    violations = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return []  # Skip binary files
    
    for line_num, line in enumerate(lines, start=1):
        # Skip if allowlisted
        if is_allowlisted(line, allowlist):
            continue
        
        for pattern, description in DRIFT_PATTERNS:
            matches = list(re.finditer(pattern, line))
            for match in matches:
                # Double-check this isn't a versioned path
                full_match = match.group(0)
                if '/api/v' in full_match:
                    continue
                
                violations.append(Violation(
                    file=str(filepath),
                    line=line_num,
                    column=match.start() + 1,
                    pattern=full_match,
                    context=line.strip()[:100],
                    remediation=f"Replace bare /api/ with /api/v1/. {description}"
                ))
    
    return violations


def scan_directory(directory: Path, file_patterns: List[str], allowlist: Set[str]) -> List[Violation]:
    """Recursively scan directory for violations."""
    all_violations = []
    
    for pattern in file_patterns:
        for filepath in directory.rglob(pattern):
            if filepath.is_file():
                violations = scan_file(filepath, allowlist)
                all_violations.extend(violations)
    
    return all_violations


def print_violations(violations: List[Violation]) -> None:
    """Print violations in a CI-friendly format."""
    if not violations:
        return
    
    print()
    print("=" * 70)
    print("API PATH DRIFT VIOLATIONS DETECTED")
    print("=" * 70)
    print()
    
    for v in violations:
        print(f"❌ {v.file}:{v.line}:{v.column}")
        print(f"   Pattern: {v.pattern}")
        print(f"   Context: {v.context}")
        print(f"   Remediation: {v.remediation}")
        print()
    
    print("=" * 70)
    print(f"Total violations: {len(violations)}")
    print()
    print("To fix:")
    print("  1. Replace /api/<endpoint> with /api/v1/<endpoint>")
    print("  2. Or add to allowlist: docs/contracts/api_path_allowlist.json")
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scan test files for API path drift violations"
    )
    parser.add_argument(
        '--directories', '-d', nargs='+',
        default=['tests/', 'e2e/', 'integration/'],
        help='Directories to scan (default: tests/, e2e/, integration/)'
    )
    parser.add_argument(
        '--patterns', '-p', nargs='+',
        default=['*.py', '*.ts', '*.js', '*.spec.ts', '*.test.ts'],
        help='File patterns to scan (default: *.py, *.ts, *.js)'
    )
    parser.add_argument(
        '--allowlist', '-a', type=str,
        default=None,
        help='Path to allowlist JSON file'
    )
    parser.add_argument(
        '--output-json', '-o', type=str,
        default=None,
        help='Output violations to JSON file'
    )
    
    args = parser.parse_args()
    
    # Find repo root
    repo_root = Path(__file__).parent.parent
    
    # Load allowlist
    allowlist_path = None
    if args.allowlist:
        allowlist_path = Path(args.allowlist)
    else:
        default_allowlist = repo_root / ALLOWLIST_FILE
        if default_allowlist.exists():
            allowlist_path = default_allowlist
    
    allowlist = load_allowlist(allowlist_path)
    
    print("=" * 70)
    print("API PATH DRIFT SCANNER")
    print("=" * 70)
    print()
    print(f"Scanning directories: {args.directories}")
    print(f"File patterns: {args.patterns}")
    if allowlist:
        print(f"Allowlist entries: {len(allowlist)}")
    print()
    
    # Scan directories
    all_violations = []
    for dir_name in args.directories:
        dir_path = repo_root / dir_name
        if dir_path.exists():
            print(f"Scanning: {dir_path}")
            violations = scan_directory(dir_path, args.patterns, allowlist)
            all_violations.extend(violations)
        else:
            print(f"Directory not found (skipping): {dir_path}")
    
    print()
    
    # Output results
    if args.output_json:
        output_data = {
            'scan_date': str(Path(__file__).stat().st_mtime),
            'violations_count': len(all_violations),
            'violations': [
                {
                    'file': v.file,
                    'line': v.line,
                    'column': v.column,
                    'pattern': v.pattern,
                    'context': v.context,
                    'remediation': v.remediation
                }
                for v in all_violations
            ]
        }
        with open(args.output_json, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Violations written to: {args.output_json}")
    
    if all_violations:
        print_violations(all_violations)
        print()
        print("❌ API PATH DRIFT CHECK FAILED")
        sys.exit(1)
    else:
        print("=" * 70)
        print("✅ API PATH DRIFT CHECK PASSED")
        print("   No bare /api/ paths detected. All paths use /api/v1/")
        print("=" * 70)
        sys.exit(0)


if __name__ == '__main__':
    main()
