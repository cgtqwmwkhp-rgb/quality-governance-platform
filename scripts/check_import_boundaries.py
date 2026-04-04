#!/usr/bin/env python3
"""Enforce architectural import boundaries between src/ layers.

Rules:
  - src/domain/ must NOT import from src/api/
  - src/domain/ must NOT import from src/infrastructure/ (except resilience)
  - src/core/ must NOT import from src/api/
  - src/core/ must NOT import from src/infrastructure/
  - src/services/ must NOT import from src/api/
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RULES: list[tuple[str, list[str], list[str]]] = [
    # (source_package, forbidden_imports, allowlist)
    ("src/domain", ["src.api"], []),
    (
        "src/domain",
        ["src.infrastructure"],
        [
            "src.infrastructure.resilience",
            "src.infrastructure.cache",
            "src.infrastructure.monitoring",
            "src.infrastructure.storage",
            "src.infrastructure.websocket",
            "src.infrastructure.tasks",
        ],
    ),
    ("src/core", ["src.api"], []),
    ("src/core", ["src.infrastructure"], []),
    ("src/services", ["src.api"], []),
]


def check_file(filepath: Path) -> list[str]:
    violations = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return violations

    rel = str(filepath)
    for node in ast.walk(tree):
        module_name = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                _check(rel, module_name, violations)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_name = node.module
            _check(rel, module_name, violations)
    return violations


def _check(filepath: str, module_name: str, violations: list[str]) -> None:
    for source_pkg, forbidden, allowlist in RULES:
        if not filepath.startswith(source_pkg):
            continue
        for forbidden_prefix in forbidden:
            if module_name.startswith(forbidden_prefix):
                if any(module_name.startswith(a) for a in allowlist):
                    continue
                violations.append(
                    f"{filepath}: illegal import '{module_name}' "
                    f"({source_pkg} must not import from {forbidden_prefix})"
                )


def main() -> int:
    root = Path(".")
    all_violations: list[str] = []

    for source_dir in ["src/domain", "src/core", "src/services"]:
        src_path = root / source_dir
        if not src_path.exists():
            continue
        for py_file in src_path.rglob("*.py"):
            all_violations.extend(check_file(py_file))

    if all_violations:
        print(f"FAIL: {len(all_violations)} import boundary violation(s):")
        for v in all_violations:
            print(f"  {v}")
        return 1

    print("OK: All import boundaries respected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
