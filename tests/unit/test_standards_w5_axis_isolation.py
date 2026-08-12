"""AST isolation: TrapGuard / ingest gate never import requirement axes."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = "standards_requirement_axis"


def _imports_module(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if FORBIDDEN in alias.name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if FORBIDDEN in mod:
                return True
    return False


def test_trap_guard_does_not_import_requirement_axis() -> None:
    path = ROOT / "src/domain/services/standards_trap_guard.py"
    assert not _imports_module(path)


def test_ingest_gate_does_not_import_requirement_axis() -> None:
    path = ROOT / "src/domain/services/standards_ingest_gate.py"
    assert not _imports_module(path)
