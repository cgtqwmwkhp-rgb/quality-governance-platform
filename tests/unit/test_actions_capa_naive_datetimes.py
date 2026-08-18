"""CAPA datetime writes in the unified Actions route must be naive UTC (PX-424).

``capa_actions.completed_at`` / ``due_date`` / ``verified_at`` are
``timestamp without time zone``. asyncpg refuses an aware datetime on those
columns and the PATCH close path 500s. SQLite accepts the same write, so the
failure is invisible locally unless this guard exists.

Incident / RTA / complaint actions use timezone-aware columns and correctly
keep ``datetime.now(timezone.utc)`` — this guard is scoped to CAPAAction
isinstance bodies, not the whole module.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime

import sqlalchemy as sa

import src.domain.models  # noqa: F401 — register mappers before reading metadata
from src.api.routes.actions import _as_capa_naive, _naive_utc_now
from src.infrastructure.database import Base

ROUTE_MODULE = pathlib.Path("src/api/routes/actions.py")

CAPA_TABLE = "capa_actions"
CAPA_NAIVE_COLUMNS = ("completed_at", "due_date", "verified_at", "created_at", "updated_at")


def _is_capa_isinstance(test: ast.AST) -> bool:
    if isinstance(test, ast.BoolOp):
        return any(_is_capa_isinstance(value) for value in test.values)
    if not isinstance(test, ast.Call):
        return False
    func = test.func
    if not isinstance(func, ast.Name) or func.id != "isinstance":
        return False
    if len(test.args) < 2:
        return False
    cls = test.args[1]
    return isinstance(cls, ast.Name) and cls.id == "CAPAAction"


def _is_aware_now_call(node: ast.AST) -> bool:
    """True for ``datetime.now(timezone.utc)`` — an arg is present."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "now"):
        return False
    return bool(node.args)


def _completed_at_assigns_aware_now(tree: ast.AST) -> list[int]:
    """Line numbers where a CAPAAction isinstance body assigns aware utcnow."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not _is_capa_isinstance(node.test):
            continue
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(child, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Attribute) and target.attr == "completed_at"
                for target in child.targets
            ):
                continue
            if _is_aware_now_call(child.value):
                lines.append(child.lineno)
    return lines


class TestCapaNaiveDatetimeConvention:
    def test_capa_datetime_columns_are_naive(self) -> None:
        table = Base.metadata.tables.get(CAPA_TABLE)
        assert table is not None, "capa_actions missing from ORM metadata"
        aware = [
            column.name
            for column in table.columns
            if column.name in CAPA_NAIVE_COLUMNS
            and isinstance(column.type, sa.DateTime)
            and getattr(column.type, "timezone", False)
        ]
        assert not aware, (
            f"capa_actions columns {aware} are timezone-aware; this guard and the "
            "Actions CAPA writers must be updated together (PX-424)."
        )

    def test_helper_returns_naive(self) -> None:
        now = _naive_utc_now()
        assert now.tzinfo is None

    def test_as_capa_naive_strips_zulu(self) -> None:
        aware = datetime.fromisoformat("2026-09-01T00:00:00+00:00")
        naive = _as_capa_naive(aware)
        assert naive is not None
        assert naive.tzinfo is None
        assert _as_capa_naive(None) is None
        already = datetime(2026, 9, 1)
        assert _as_capa_naive(already) == already

    def test_capa_isinstance_bodies_do_not_assign_aware_completed_at(self) -> None:
        source = ROUTE_MODULE.read_text()
        tree = ast.parse(source, filename=str(ROUTE_MODULE))
        violations = _completed_at_assigns_aware_now(tree)
        assert not violations, (
            "CAPAAction isinstance bodies assign datetime.now(timezone.utc) to "
            f"completed_at at lines {violations}. asyncpg 500s on that write "
            "(PX-424). Use _naive_utc_now()."
        )

    def test_timezone_utc_now_still_used_for_aware_action_tables(self) -> None:
        """Incident/RTA/complaint completed_at stays aware — do not naive the whole file."""
        from datetime import timezone as tz

        aware = datetime.now(tz.utc)
        assert aware.tzinfo is not None
        source = ROUTE_MODULE.read_text()
        assert "datetime.now(timezone.utc)" in source
