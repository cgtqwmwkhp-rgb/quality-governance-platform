#!/usr/bin/env python3
"""Validate Alembic migration filenames start with a date prefix (YYYYMMDD or YYYY-MM-DD)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_DIR = ROOT / "alembic" / "versions"

# Filename (without .py) must start with either compact or ISO date prefix.
_PATTERNS = (
    re.compile(r"^\d{8}"),  # YYYYMMDD (optionally followed by time, underscore, revision, etc.)
    re.compile(r"^\d{4}-\d{2}-\d{2}"),  # YYYY-MM-DD
)


def _stem(name: str) -> str:
    return Path(name).stem


def is_valid_migration_filename(filename: str) -> bool:
    if filename == "__init__.py":
        return True
    stem = _stem(filename)
    return any(p.match(stem) for p in _PATTERNS)


def main() -> int:
    if not VERSIONS_DIR.is_dir():
        print(f"ERROR: migrations directory not found: {VERSIONS_DIR}", file=sys.stderr)
        return 1

    py_files = sorted(
        p
        for p in VERSIONS_DIR.rglob("*.py")
        if p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts
    )

    bad = [p for p in py_files if not is_valid_migration_filename(p.name)]

    checked = len(py_files)
    violation_count = len(bad)

    for path in bad:
        rel = path.relative_to(VERSIONS_DIR)
        print(f"VIOLATION: {rel}", file=sys.stderr)

    print(f"{checked} migrations checked, {violation_count} violations")

    return 1 if violation_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
