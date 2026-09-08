"""The investigation RCA endpoints and the router wiring (INV-C10).

The route functions are driven directly against a SQLite session — the idiom
INV-C7 findings tests use — with the tenancy helper patched. The tenancy check
itself is ``_get_investigation_or_404`` in ``investigations.py``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.routes import investigation_rca as routes
from src.api.schemas.investigation_rca import InvestigationRcaUpsert
from src.domain.exceptions import AuthorizationError
from src.domain.models.investigation import InvestigationRun
from src.domain.models.rca_tools import FiveWhysAnalysis

try:
    from fastapi.routing import iter_route_contexts as _iter_route_contexts
except ImportError:

    def _iter_route_contexts(routes: Any) -> Any:
        return routes


REPO_ROOT = Path(__file__).resolve().parents[2]
TENANT = 7
USER = SimpleNamespace(id=11, tenant_id=TENANT, is_superuser=False)
_PATH_CONVERTER = re.compile(r":(?:int|str|float|path|uuid)\}")


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(FiveWhysAnalysis.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


async def _seed_run(db: AsyncSession, data=None) -> InvestigationRun:
    run = InvestigationRun(
        id=7,
        tenant_id=TENANT,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42,
        status="in_progress",
        title="Fork lift near miss",
        reference_number="INV-7",
        data={} if data is None else data,
        version=1,
    )
    db.add(run)
    await db.commit()
    return run


def _authorised(run: InvestigationRun):
    return patch.object(routes, "_get_investigation_or_404", new=AsyncMock(return_value=run))


@pytest.mark.asyncio
async def test_listing_a_run_with_no_rca_is_a_success_with_empty_whys(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        payload = await routes.get_investigation_rca(7, db_session, USER)

    assert payload["analysis_id"] is None
    assert payload["investigation_id"] == 7
    assert payload["why_1"] == ""
    assert [item["answer"] for item in payload["whys"][:5]] == ["", "", "", "", ""]


@pytest.mark.asyncio
async def test_listing_converts_the_legacy_strings_once_and_commits_them(session_factory):
    async with session_factory() as first_session:
        run = await _seed_run(first_session, data={"why_1": "the interlock was bypassed"})
        with _authorised(run):
            first = await routes.get_investigation_rca(7, first_session, USER)
            second = await routes.get_investigation_rca(7, first_session, USER)

    assert first["why_1"] == "the interlock was bypassed"
    assert first["analysis_id"] == second["analysis_id"]

    async with session_factory() as later_session:
        reloaded = await later_session.get(InvestigationRun, 7)
        with _authorised(reloaded):
            third = await routes.get_investigation_rca(7, later_session, USER)
        stored = await later_session.scalar(select(func.count(FiveWhysAnalysis.id)))

    assert third["why_1"] == "the interlock was bypassed"
    assert stored == 1


@pytest.mark.asyncio
async def test_put_returns_the_analysis_and_dual_writes_the_strings(db_session):
    run = await _seed_run(db_session)
    body = InvestigationRcaUpsert(
        problem_statement="fork lift struck a pedestrian",
        whys=[{"level": 1, "answer": "the interlock was bypassed", "evidence": "CCTV still 14:02"}],
        root_cause="no banksman",
        contributing_factors="",
    )
    with _authorised(run):
        payload = await routes.put_investigation_rca(7, body, db_session, USER)

    assert payload["why_1"] == "the interlock was bypassed"
    assert payload["whys"][0]["evidence"] == "CCTV still 14:02"
    assert payload["root_cause"] == "no banksman"
    assert run.data["why_1"] == "the interlock was bypassed"
    assert run.data["sections"]["section_4_root_cause"]["why_1"] == "the interlock was bypassed"
    assert run.data["sections"]["rca"]["why_1"] == "the interlock was bypassed"


@pytest.mark.asyncio
async def test_put_without_a_tenant_is_refused_not_stored(db_session):
    await _seed_run(db_session)
    # A run object that is not the ORM row: assigning ``tenant_id = None`` on
    # the mapped instance would flush a NOT NULL violation before the handler
    # can refuse. The handler only reads ``id`` / ``tenant_id``.
    ghost = SimpleNamespace(id=7, tenant_id=None)
    body = InvestigationRcaUpsert(whys=[{"level": 1, "answer": "hijacked"}])
    with _authorised(ghost):
        with pytest.raises(AuthorizationError):
            await routes.put_investigation_rca(7, body, db_session, USER)
    assert await db_session.scalar(select(func.count(FiveWhysAnalysis.id))) == 0


def test_duplicate_why_levels_are_refused_by_the_schema():
    with pytest.raises(ValueError):
        InvestigationRcaUpsert(
            whys=[
                {"level": 1, "answer": "one"},
                {"level": 1, "answer": "also one"},
            ]
        )


def test_unknown_fields_are_forbidden_on_the_upsert():
    with pytest.raises(ValueError):
        InvestigationRcaUpsert(capa_per_why="no")  # type: ignore[call-arg]


def test_every_rca_endpoint_declares_a_permission():
    tree = ast.parse((REPO_ROOT / "src/api/routes/investigation_rca.py").read_text(encoding="utf-8"))
    tokens = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "require_permission"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert tokens == {"investigation:update"}

    decorated = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and any(isinstance(d, ast.Call) for d in node.decorator_list)
    ]
    assert len(decorated) == 2, "get, put"
    for handler in decorated:
        source = ast.dump(handler)
        assert "require_permission" in source, f"{handler.name} is not permission-gated"


def test_the_rca_paths_are_mounted_where_the_client_calls_them():
    from src.main import app

    rca = {
        (method, _PATH_CONVERTER.sub("}", route.path))
        for route in _iter_route_contexts(app.routes)
        for method in getattr(route, "methods", set()) or set()
        if "/investigations/" in getattr(route, "path", "") and route.path.rstrip("/").endswith("/rca")
    }
    assert rca == {
        ("GET", "/api/v1/investigations/{investigation_id}/rca"),
        ("PUT", "/api/v1/investigations/{investigation_id}/rca"),
    }
