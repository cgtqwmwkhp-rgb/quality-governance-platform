"""INV-C11: CAPA per Why on ``capa_actions`` (DEC-2).

SQLite-backed for the Why lookup and empty-Why refusal. The alembic head and
DDL tests follow the INV-C7 findings-rows idiom.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.routes import investigation_rca as routes
from src.api.schemas.investigation_rca import CreateCapaFromWhyRequest
from src.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from src.domain.models.capa import CAPAAction
from src.domain.models.investigation import InvestigationRun
from src.domain.models.rca_tools import FiveWhysAnalysis
from src.domain.services.capa_service import CAPAService
from src.domain.services.investigation_rca_service import why_answer_at_level

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20261121_inv_c11_capa_per_why.py"
REVISION = "20261121_inv_c11_capa_why"
NEW_COLUMNS = {
    "five_whys_id",
    "why_level",
    "effectiveness_review_date",
    "is_effective",
    "effectiveness_notes",
}
TENANT = 7
USER = SimpleNamespace(id=11, tenant_id=TENANT, is_superuser=False)

_HEADS_RUNNER = r"""
import json, sys
from alembic.config import Config
from alembic.script import ScriptDirectory

repo = sys.argv[1]
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
    # The chain tip moves as later revisions land; the assertion under test is
    # that there is exactly one of them. Currently INV-C17.
    chain = _alembic_chain(tmp_path)
    assert chain["heads"] == ["20261122_inv_c17_issue"], f"expected a single head, found {chain['heads']}"
    assert chain["parents"] == ["20261120_inv_c7_findings"]


def test_the_migration_only_adds_and_never_rewrites() -> None:
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    called = {
        node.func.attr
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "add_column" in called
    for forbidden in ("alter_column", "drop_column", "drop_table", "bulk_insert", "execute"):
        assert forbidden not in called, f"upgrade() calls op.{forbidden} — this revision is additive only"


def test_the_downgrade_drops_only_the_new_columns() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "NEW_COLUMNS" in source
    for column in NEW_COLUMNS:
        assert column in source
    tree = ast.parse(source)
    downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    dumped = ast.dump(downgrade)
    assert "drop_column" in dumped
    assert "drop_table" not in dumped
    assert "investigation_runs" not in dumped
    assert "five_whys_analyses" not in dumped


def test_the_model_declares_the_new_columns() -> None:
    names = {column.name for column in CAPAAction.__table__.columns}
    assert NEW_COLUMNS <= names
    assert CAPAAction.__table__.c.five_whys_id.nullable is True
    assert CAPAAction.__table__.c.why_level.nullable is True
    assert CAPAAction.__table__.c.is_effective.nullable is True


def test_why_answer_at_level_does_not_invent_text() -> None:
    assert why_answer_at_level(None, 1) == ""
    assert why_answer_at_level([], 1) == ""
    assert why_answer_at_level([{"level": 1, "answer": "  "}], 1) == ""
    assert why_answer_at_level([{"level": 1, "answer": "the interlock was bypassed"}], 1) == (
        "the interlock was bypassed"
    )
    assert why_answer_at_level([{"level": 1, "answer": "the interlock was bypassed"}], 2) == ""


def test_create_capa_from_why_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        CreateCapaFromWhyRequest(why_level=1, invented="no")  # type: ignore[call-arg]


def test_create_capa_from_why_request_rejects_assignee_fields_it_cannot_echo() -> None:
    """Guard 4: do not advertise assignee_* on create-from-Why; CAPAResponse uses assigned_to_id."""
    with pytest.raises(ValueError):
        CreateCapaFromWhyRequest(why_level=1, assignee_id=9)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        CreateCapaFromWhyRequest(why_level=1, assignee_name="Pat")  # type: ignore[call-arg]


def test_create_capa_from_why_request_requires_why_level() -> None:
    with pytest.raises(ValueError):
        CreateCapaFromWhyRequest()


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(FiveWhysAnalysis.__table__.create)
        await conn.run_sync(CAPAAction.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


async def _seed_run_with_why(db: AsyncSession, *, answer: str = "the interlock was bypassed") -> InvestigationRun:
    run = InvestigationRun(
        id=7,
        tenant_id=TENANT,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42,
        status="in_progress",
        title="Fork lift near miss",
        reference_number="INV-7",
        data={"why_1": answer} if answer else {},
        version=1,
    )
    db.add(run)
    await db.flush()
    analysis = FiveWhysAnalysis(
        tenant_id=TENANT,
        investigation_id=7,
        problem_statement="fork lift struck a pedestrian",
        whys=[{"level": 1, "why": "", "answer": answer, "evidence": None}] if answer else [],
        primary_root_cause="no banksman" if answer else None,
        created_by_id=11,
        updated_by_id=11,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return run


def _authorised(run: InvestigationRun):
    return patch.object(routes, "_get_investigation_or_404", new=AsyncMock(return_value=run))


def _applied_capa_patches():
    stack = ExitStack()
    stack.enter_context(
        patch(
            "src.domain.services.capa_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0111"),
        )
    )
    stack.enter_context(patch("src.domain.services.capa_service.record_audit_event", new=AsyncMock()))
    stack.enter_context(patch("src.domain.services.capa_service.invalidate_tenant_cache", new=AsyncMock()))
    stack.enter_context(patch("src.domain.services.capa_service.track_metric"))
    return stack


@pytest.mark.asyncio
async def test_create_capa_from_why_stores_the_why_link(db_session):
    run = await _seed_run_with_why(db_session)
    body = CreateCapaFromWhyRequest(why_level=1)
    with _authorised(run), _applied_capa_patches():
        capa = await routes.create_capa_from_why(7, body, db_session, USER)

    assert capa.why_level == 1
    assert capa.five_whys_id is not None
    assert "the interlock was bypassed" in capa.title
    stored = await db_session.scalar(select(func.count(CAPAAction.id)))
    assert stored == 1


@pytest.mark.asyncio
async def test_empty_why_is_refused_and_invents_nothing(db_session):
    run = await _seed_run_with_why(db_session, answer="")
    body = CreateCapaFromWhyRequest(why_level=1)
    with _authorised(run), _applied_capa_patches():
        with pytest.raises(ValidationError, match="not invented"):
            await routes.create_capa_from_why(7, body, db_session, USER)
    assert await db_session.scalar(select(func.count(CAPAAction.id))) == 0


@pytest.mark.asyncio
async def test_empty_why_does_not_500_when_the_client_sends_a_title(db_session):
    run = await _seed_run_with_why(db_session, answer="")
    body = CreateCapaFromWhyRequest(why_level=1, title="please invent this")
    with _authorised(run), _applied_capa_patches():
        with pytest.raises(ValidationError, match="not invented"):
            await routes.create_capa_from_why(7, body, db_session, USER)
    assert await db_session.scalar(select(func.count(CAPAAction.id))) == 0


@pytest.mark.asyncio
async def test_another_tenants_analysis_is_invisible(db_session):
    run = InvestigationRun(
        id=7,
        tenant_id=TENANT,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42,
        status="in_progress",
        title="Fork lift near miss",
        reference_number="INV-7",
        data={},
        version=1,
    )
    db_session.add(run)
    db_session.add(
        FiveWhysAnalysis(
            tenant_id=99,
            investigation_id=7,
            problem_statement="other org",
            whys=[{"level": 1, "why": "", "answer": "stolen why", "evidence": None}],
            created_by_id=11,
            updated_by_id=11,
        )
    )
    await db_session.commit()
    body = CreateCapaFromWhyRequest(why_level=1)
    with _authorised(run), _applied_capa_patches():
        with pytest.raises(ValidationError, match="No RCA analysis"):
            await routes.create_capa_from_why(7, body, db_session, USER)
    assert await db_session.scalar(select(func.count(CAPAAction.id))) == 0


@pytest.mark.asyncio
async def test_missing_tenant_is_refused_not_stored(db_session):
    await _seed_run_with_why(db_session)
    ghost = SimpleNamespace(id=7, tenant_id=None)
    body = CreateCapaFromWhyRequest(why_level=1)
    with _authorised(ghost), _applied_capa_patches():
        with pytest.raises(AuthorizationError):
            await routes.create_capa_from_why(7, body, db_session, USER)
    assert await db_session.scalar(select(func.count(CAPAAction.id))) == 0


@pytest.mark.asyncio
async def test_mismatched_five_whys_id_is_not_found(db_session):
    run = await _seed_run_with_why(db_session)
    body = CreateCapaFromWhyRequest(why_level=1, five_whys_id=999)
    with _authorised(run), _applied_capa_patches():
        with pytest.raises(NotFoundError):
            await routes.create_capa_from_why(7, body, db_session, USER)
    assert await db_session.scalar(select(func.count(CAPAAction.id))) == 0


@pytest.mark.asyncio
async def test_service_create_from_why_sets_effectiveness_columns_null():
    investigation = InvestigationRun(
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=10,
        title="Slip",
        description="Wet floor",
        status="in_progress",
        tenant_id=1,
        created_by_id=2,
        updated_by_id=2,
        reference_number="INV-1",
    )
    investigation.id = 55
    analysis = SimpleNamespace(
        id=11,
        tenant_id=1,
        investigation_id=55,
        whys=[{"level": 2, "why": "", "answer": "guard was removed", "evidence": ""}],
    )
    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation
    analysis_result = MagicMock()
    analysis_result.scalars.return_value.first.return_value = analysis

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[inv_result, analysis_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = CAPAService(db)
    with (
        patch(
            "src.domain.services.capa_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0112"),
        ),
        patch("src.domain.services.capa_service.record_audit_event", new=AsyncMock()),
        patch("src.domain.services.capa_service.invalidate_tenant_cache", new=AsyncMock()),
        patch("src.domain.services.capa_service.track_metric"),
    ):
        capa = await svc.create_capa_from_why(
            55,
            user_id=2,
            tenant_id=1,
            why_level=2,
        )

    assert capa.five_whys_id == 11
    assert capa.why_level == 2
    assert capa.is_effective is None
    assert capa.effectiveness_notes is None
    assert capa.effectiveness_review_date is None
    assert "guard was removed" in capa.title
