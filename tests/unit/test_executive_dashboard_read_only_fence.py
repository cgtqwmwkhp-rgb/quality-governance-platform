"""B-14: ExecutiveDashboardService must only be constructed on read-only paths.

``_recover_session`` rolls the shared request session back after a failed
sub-query. That is safe only when nothing pending is on the session. The
runtime fence catches a dirty session at construction; the AST walk keeps the
route surface honest so the fence is never needed in production.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.domain.services.executive_dashboard import ExecutiveDashboardService

ROUTES_DIR = Path("src/api/routes")


def test_construction_on_clean_session_succeeds():
    db = SimpleNamespace(new=set(), dirty=set(), deleted=set())
    service = ExecutiveDashboardService(db, tenant_id=1)
    assert service.tenant_id == 1


def test_construction_on_pending_write_raises():
    pending = object()
    db = SimpleNamespace(new={pending}, dirty=set(), deleted=set())

    with pytest.raises(RuntimeError, match="pending write"):
        ExecutiveDashboardService(db, tenant_id=1)


def test_duck_typed_session_without_identity_sets_still_constructs():
    """Hand-rolled test fakes omit new/dirty/deleted; getattr defaults must keep them working."""
    db = SimpleNamespace()
    service = ExecutiveDashboardService(db, tenant_id=None)
    assert service.db is db


def _route_methods(tree: ast.AST) -> list[ast.AsyncFunctionDef | ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))]


def _calls_executive_dashboard(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name) and func.id == "ExecutiveDashboardService":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "ExecutiveDashboardService":
            return True
    return False


def _http_methods(node: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    methods: set[str] = set()
    for decorator in node.decorator_list:
        target = decorator
        if isinstance(decorator, ast.Call):
            target = decorator.func
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id in {"router", "app"} and target.attr in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
            }:
                methods.add(target.attr)
        if isinstance(target, ast.Name) and target.id in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
        }:
            methods.add(target.id)
    return methods


def test_every_route_constructing_executive_dashboard_is_a_get():
    offenders: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _route_methods(tree):
            if not _calls_executive_dashboard(node):
                continue
            methods = _http_methods(node)
            if methods != {"get"}:
                offenders.append(f"{path.name}:{node.name}:{sorted(methods) or ['<no-http-decorator>']}")

    assert offenders == [], (
        "ExecutiveDashboardService rolls back the shared session on sub-query "
        f"failure; only GET routes may construct it. Offenders: {offenders}"
    )
