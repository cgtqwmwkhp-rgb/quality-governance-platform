"""The findings endpoints, the router wiring, and the migration (INV-C7).

The route functions are driven directly against a SQLite session — the idiom the
PX-141 revision-event and INV-C4 nested-write tests use — with the tenancy helper
patched, because what is under test here is the handler contract (status codes,
the list every mutation returns, the refusals), not the tenancy check itself.
That check is ``_get_investigation_or_404`` in ``investigations.py``, which this
module imports rather than re-implements and which has its own tests.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.routes import investigation_findings as routes
from src.api.schemas.investigation_finding import (
    InvestigationFindingCreate,
    InvestigationFindingReorderRequest,
    InvestigationFindingUpdate,
)
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.investigation import InvestigationRun
from src.domain.models.investigation_finding import InvestigationFinding

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20261120_inv_c7_findings_rows.py"
REVISION = "20261120_inv_c7_findings"

TENANT = 7
USER = SimpleNamespace(id=11, tenant_id=TENANT, is_superuser=False)


@pytest.fixture
async def session_factory():
    # ``StaticPool`` so every session in a test shares one connection: an ordinary
    # in-memory SQLite pool hands each session its own empty database, and the
    # commit assertions below need a second session to see what the first wrote.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(InvestigationFinding.__table__.create)
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


# --------------------------------------------------------------------------- #
# Handler contract
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_listing_a_run_with_no_findings_is_a_success_with_an_empty_list(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        payload = await routes.list_investigation_findings(7, db_session, USER)

    assert payload == {"items": [], "total": 0, "investigation_id": 7, "findings_text": ""}


@pytest.mark.asyncio
async def test_listing_converts_the_legacy_string_once_and_commits_it(session_factory):
    """The conversion must survive the request that made it, and not repeat."""
    async with session_factory() as first_session:
        run = await _seed_run(first_session, data={"findings": "1. Guard was removed\n2. No banksman"})
        with _authorised(run):
            first = await routes.list_investigation_findings(7, first_session, USER)
            second = await routes.list_investigation_findings(7, first_session, USER)

    assert [item["body"] for item in first["items"]] == ["Guard was removed", "No banksman"]
    assert [item["id"] for item in second["items"]] == [item["id"] for item in first["items"]]

    # A later request, on its own session, finds the rows already there and does
    # not convert a second time.
    async with session_factory() as later_session:
        reloaded = await later_session.get(InvestigationRun, 7)
        with _authorised(reloaded):
            third = await routes.list_investigation_findings(7, later_session, USER)
        stored = await later_session.scalar(select(func.count(InvestigationFinding.id)))

    assert third["total"] == 2
    assert stored == 2
    assert reloaded.data["findings"] == "1. Guard was removed\n2. No banksman"


@pytest.mark.asyncio
async def test_create_returns_the_whole_ordered_list_with_the_derived_text(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_finding(
            7, InvestigationFindingCreate(body="Guard was removed"), db_session, USER
        )
        payload = await routes.create_investigation_finding(
            7, InvestigationFindingCreate(body="No banksman"), db_session, USER
        )

    assert [item["body"] for item in payload["items"]] == ["Guard was removed", "No banksman"]
    assert [item["sort_order"] for item in payload["items"]] == [0, 1]
    assert payload["findings_text"] == "1. Guard was removed\n2. No banksman"
    assert run.data["findings"] == payload["findings_text"]


@pytest.mark.asyncio
async def test_update_and_delete_report_a_finding_that_is_not_this_runs_as_missing(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        with pytest.raises(NotFoundError):
            await routes.update_investigation_finding(
                7, 4242, InvestigationFindingUpdate(body="hijacked"), db_session, USER
            )
        with pytest.raises(NotFoundError):
            await routes.delete_investigation_finding(7, 4242, db_session, USER)


@pytest.mark.asyncio
async def test_delete_returns_the_remaining_list(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        created = await routes.create_investigation_finding(
            7, InvestigationFindingCreate(body="only one"), db_session, USER
        )
        payload = await routes.delete_investigation_finding(7, created["items"][0]["id"], db_session, USER)

    assert payload["items"] == []
    assert payload["findings_text"] == ""
    assert run.data["findings"] == ""


@pytest.mark.asyncio
async def test_reorder_applies_and_refuses_a_mismatched_list(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_finding(7, InvestigationFindingCreate(body="one"), db_session, USER)
        listed = await routes.create_investigation_finding(7, InvestigationFindingCreate(body="two"), db_session, USER)
        ids = [item["id"] for item in listed["items"]]

        payload = await routes.reorder_investigation_findings(
            7, InvestigationFindingReorderRequest(finding_ids=list(reversed(ids))), db_session, USER
        )
        assert [item["body"] for item in payload["items"]] == ["two", "one"]

        with pytest.raises(BadRequestError):
            await routes.reorder_investigation_findings(
                7, InvestigationFindingReorderRequest(finding_ids=[ids[0]]), db_session, USER
            )

    # The refusal left the applied order in place rather than half-applying.
    with _authorised(run):
        after = await routes.list_investigation_findings(7, db_session, USER)
    assert [item["body"] for item in after["items"]] == ["two", "one"]


def test_a_blank_body_is_refused_by_the_schema_not_stored_as_an_empty_finding():
    with pytest.raises(ValueError):
        InvestigationFindingCreate(body="")
    with pytest.raises(ValueError):
        InvestigationFindingCreate(body="text", sort_order=3)  # type: ignore[call-arg]


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #


def test_every_findings_endpoint_declares_a_permission():
    """``AUTHENTICATED_ONLY_DEBT`` is at its ceiling: a new route must gate itself."""
    tree = ast.parse((REPO_ROOT / "src/api/routes/investigation_findings.py").read_text(encoding="utf-8"))
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
    assert len(decorated) == 5, "list, create, update, delete, reorder"
    for handler in decorated:
        source = ast.dump(handler)
        assert "require_permission" in source, f"{handler.name} is not permission-gated"


#: Drops the Starlette path converter (``{id:int}`` → ``{id}``) so the assertion below
#: reads as the URL the frontend calls. Done here rather than by reading Starlette's
#: own ``path_format``: that attribute is an implementation detail nothing else in this
#: repository touches, and it is gone in the starlette 1.3.1 / fastapi 0.140.7 that CI
#: resolves out of the unpinned ``fastapi>=0.109.0,<1.0.0`` range, while a local venv on
#: starlette 0.52.1 still has it. Reading it made this test pass locally and match
#: nothing at all in CI. Every other route census in the suite reads ``route.path``.
_PATH_CONVERTER = re.compile(r":(?:int|str|float|path|uuid)\}")


def test_the_findings_paths_are_mounted_where_the_client_calls_them():
    from src.main import app

    findings = {
        (method, _PATH_CONVERTER.sub("}", route.path))
        for route in app.routes
        for method in getattr(route, "methods", set()) or set()
        if "/investigations/" in getattr(route, "path", "") and "findings" in route.path
    }
    assert findings == {
        ("GET", "/api/v1/investigations/{investigation_id}/findings"),
        ("POST", "/api/v1/investigations/{investigation_id}/findings"),
        ("PATCH", "/api/v1/investigations/{investigation_id}/findings/{finding_id}"),
        ("DELETE", "/api/v1/investigations/{investigation_id}/findings/{finding_id}"),
        ("POST", "/api/v1/investigations/{investigation_id}/findings/reorder"),
    }


# --------------------------------------------------------------------------- #
# Migration
# --------------------------------------------------------------------------- #

#: Asks Alembic for the chain rather than re-implementing its parser, the same
#: probe ``test_audit_capture_join.py`` uses. Run out of process and out of the
#: repo directory because the repository's own ``alembic/`` package shadows the
#: installed one on ``sys.path`` when the cwd is the repo root.
_HEADS_RUNNER = r"""
import json, sys
from alembic.config import Config
from alembic.script import ScriptDirectory

repo = sys.argv[1]
# Some revisions import ``src.*`` at module scope, which ScriptDirectory loads.
sys.path.append(repo)
cfg = Config(repo + "/alembic.ini")
cfg.set_main_option("script_location", repo + "/alembic")
script = ScriptDirectory.from_config(cfg)
print(json.dumps({
    "heads": sorted(script.get_heads()),
    "parents": sorted(script.get_revision(sys.argv[2])._all_down_revisions or ()),
}))
"""


def _alembic_chain(tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-c", _HEADS_RUNNER, str(REPO_ROOT), REVISION],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        pytest.fail(f"alembic head probe failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


def test_the_new_revision_is_the_only_head(tmp_path) -> None:
    """A second head makes ``alembic upgrade head`` refuse — on deploy, not here."""
    chain = _alembic_chain(tmp_path)
    assert chain["heads"] == [REVISION], f"expected a single head, found {chain['heads']}"
    assert chain["parents"] == ["20260903_asm_plant_evid"]


def test_the_migration_only_adds_and_never_rewrites() -> None:
    """Expand half of expand/contract: no column altered, no row touched."""
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    called = {
        node.func.attr
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "create_table" in called
    for forbidden in ("alter_column", "add_column", "drop_column", "drop_table", "bulk_insert", "execute"):
        assert forbidden not in called, f"upgrade() calls op.{forbidden} — this revision is additive only"


def test_the_downgrade_drops_only_the_new_table() -> None:
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    dropped = [
        node.args[0].value
        for node in ast.walk(downgrade)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "drop_table"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert dropped == ["investigation_findings"] or dropped == []
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'TABLE = "investigation_findings"' in source


@pytest.mark.asyncio
async def test_the_migration_and_the_model_declare_the_same_columns() -> None:
    """Schema drift between the ORM and the DDL is the failure nobody sees until prod."""
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    ddl_columns = {
        node.args[0].value
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Column"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert ddl_columns == {column.name for column in InvestigationFinding.__table__.columns}


def test_the_upgrade_and_downgrade_emit_valid_postgres_ddl(tmp_path) -> None:
    """Run both halves for real, capturing the SQL a Postgres deploy would execute.

    Not executed against SQLite: the timestamp defaults are ``now()``, which is the
    target dialect and not SQLite's, so a SQLite round trip could only pass by
    weakening the DDL to suit the test. The upgrade *is* executed for real against
    Postgres 16 by the ``alembic-check`` CI job (``alembic upgrade head``); this
    covers the half that job never runs — the downgrade — and proves both compile
    for the dialect that will run them.

    ``_table_exists`` is stubbed because offline mode has no inspectable bind. That
    is the only thing replaced; the ``op`` calls themselves are the real ones.
    """
    script = r"""
import importlib.util, io, sys
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

spec = importlib.util.spec_from_file_location("inv_c7_migration", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def render(direction, exists):
    module._table_exists = lambda: exists
    buffer = io.StringIO()
    ctx = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(ctx):
        getattr(module, direction)()
    return buffer.getvalue()

up = render("upgrade", False)
down = render("downgrade", True)
print(repr({"up": up, "down": down, "up_noop": render("upgrade", True),
            "down_noop": render("downgrade", False)}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(MIGRATION_PATH)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, f"stdout={completed.stdout}\nstderr={completed.stderr}"
    rendered = ast.literal_eval(completed.stdout.strip())

    assert "CREATE TABLE investigation_findings" in rendered["up"]
    for column in InvestigationFinding.__table__.columns:
        assert column.name in rendered["up"]
    assert "ON DELETE CASCADE" in rendered["up"]
    assert "CREATE INDEX ix_investigation_findings_run_order" in rendered["up"]

    assert "DROP TABLE investigation_findings" in rendered["down"]
    # The down script touches nothing else. This is the assertion that would fail
    # if a later edit made downgrade "tidy up" a column somewhere.
    assert "ALTER TABLE" not in rendered["down"]

    # Both halves are safe to re-run: the guard makes them no-ops.
    assert rendered["up_noop"].strip() == ""
    assert rendered["down_noop"].strip() == ""
