"""Guardrails: near_miss + policies write routes use require_permission."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _permission_depends(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "require_permission":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
        if isinstance(func, ast.Attribute) and func.attr == "require_permission":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
    return found


def test_near_miss_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/near_miss.py")
    assert "near_miss:create" in perms
    assert "near_miss:update" in perms


def test_policies_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/policies.py")
    assert "policy:create" in perms
    assert "policy:update" in perms
    assert "policy:delete" in perms
