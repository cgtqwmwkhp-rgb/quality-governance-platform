"""RCA lives on ``five_whys_analyses``, and the leftover Why strings still read (INV-C10).

SQLite-backed: only ``investigation_runs`` and ``five_whys_analyses`` are created.
SQLite does not enforce the FK targets those tables carry.

What is being defended here, in order of what would hurt most if it broke:

* a conversion that invents Why text from an empty investigation;
* a conversion that runs twice and duplicates the analysis;
* a tenant filter that only exists on the parent lookup;
* a ``why_1`` string that stops tracking the analysis, so C13/C18 readers print
  stale RCA after the investigator cleared it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.investigation import InvestigationRun
from src.domain.models.rca_tools import FiveWhysAnalysis
from src.domain.services.investigation_rca_service import (
    InvestigationRcaService,
    sync_rca_workspace_fields,
    workspace_whys,
)

TENANT = 7
OTHER_TENANT = 9
ROOT_CAUSE_SECTION = "section_4_root_cause"
LEGACY_RCA_SECTION = "rca"


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(FiveWhysAnalysis.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def _run(db: AsyncSession, *, run_id: int = 1, tenant_id: int = TENANT, data=None) -> InvestigationRun:
    run = InvestigationRun(
        id=run_id,
        tenant_id=tenant_id,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42 + run_id,
        status="in_progress",
        title="Fork lift near miss",
        reference_number=f"INV-{run_id}",
        data={} if data is None else data,
        version=1,
    )
    db.add(run)
    await db.flush()
    return run


def _answers(payload: dict) -> list[str]:
    return [item["answer"] for item in payload["whys"][:5]]


# --------------------------------------------------------------------------- #
# Sync — dual-write of the leftover strings
# --------------------------------------------------------------------------- #


def test_sync_writes_flat_and_both_rca_sections():
    out = sync_rca_workspace_fields({}, {"why_1": "the interlock was bypassed", "root_cause": "no banksman"})
    assert out["why_1"] == "the interlock was bypassed"
    assert out["root_cause"] == "no banksman"
    for section in (ROOT_CAUSE_SECTION, LEGACY_RCA_SECTION):
        assert out["sections"][section]["why_1"] == "the interlock was bypassed"
        assert out["sections"][section]["root_cause"] == "no banksman"


def test_sync_clears_stale_nested_text_when_the_analysis_is_empty():
    """The analysis is the author: an empty Why must not leave the nested string standing."""
    out = sync_rca_workspace_fields(
        {"why_1": "stale", "sections": {ROOT_CAUSE_SECTION: {"why_1": "stale nested"}}},
        {"why_1": ""},
    )
    assert out["why_1"] == ""
    assert out["sections"][ROOT_CAUSE_SECTION]["why_1"] == ""


def test_sync_does_not_invent_sections_just_to_hold_blanks():
    out = sync_rca_workspace_fields({"conclusion": "unsafe system of work"}, {"why_1": ""})
    assert out["why_1"] == ""
    assert "sections" not in out


def test_workspace_whys_pads_missing_levels_without_inventing_answers():
    slots = workspace_whys([{"level": 2, "answer": "deeper cause", "evidence": "photo"}])
    assert [item["level"] for item in slots[:5]] == [1, 2, 3, 4, 5]
    assert slots[0]["answer"] == ""
    assert slots[1]["answer"] == "deeper cause"
    assert slots[1]["evidence"] == "photo"


# --------------------------------------------------------------------------- #
# Empty is honest
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_an_investigation_with_no_rca_lists_empty_rather_than_failing(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert payload["analysis_id"] is None
        assert _answers(payload) == ["", "", "", "", ""]
        assert payload["why_1"] == ""
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 0
        assert run.data == {}


@pytest.mark.asyncio
async def test_whitespace_legacy_strings_invent_no_analysis(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"why_1": "   ", "root_cause": "\n"})
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert payload["analysis_id"] is None
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 0
        assert run.data == {"why_1": "   ", "root_cause": "\n"}


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_flat_why_strings_convert_on_first_read(session_factory):
    async with session_factory() as db:
        run = await _run(
            db,
            data={
                "why_1": "the interlock was bypassed",
                "why_2": "the guard had been removed",
                "root_cause": "no banksman",
                "problem_statement": "fork lift struck a pedestrian",
            },
        )
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert payload["analysis_id"] is not None
        assert payload["why_1"] == "the interlock was bypassed"
        assert payload["why_2"] == "the guard had been removed"
        assert payload["root_cause"] == "no banksman"
        assert payload["problem_statement"] == "fork lift struck a pedestrian"
        assert payload["whys"][0]["evidence"] == ""
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 1


@pytest.mark.asyncio
async def test_nested_only_why_strings_convert_too(session_factory):
    async with session_factory() as db:
        run = await _run(
            db,
            data={"sections": {ROOT_CAUSE_SECTION: {"why_1": "Nested why one"}}},
        )
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert payload["why_1"] == "Nested why one"
        assert payload["whys"][0]["answer"] == "Nested why one"


@pytest.mark.asyncio
async def test_conversion_does_not_repeat_on_every_read(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"why_1": "the interlock was bypassed"})
        first = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        second = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert first["analysis_id"] == second["analysis_id"]
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 1


@pytest.mark.asyncio
async def test_conversion_does_not_invent_why_questions(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"why_1": "the interlock was bypassed"})
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert payload["whys"][0]["why"] == ""
        assert payload["whys"][0]["answer"] == "the interlock was bypassed"


# --------------------------------------------------------------------------- #
# Upsert + dual-write
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_upsert_writes_analysis_and_dual_writes_legacy_strings(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        payload = await InvestigationRcaService.upsert_workspace(
            db,
            investigation=run,
            tenant_id=TENANT,
            problem_statement="fork lift struck a pedestrian",
            whys=[
                {"level": 1, "answer": "the interlock was bypassed", "evidence": "CCTV still 14:02"},
                {"level": 2, "answer": "the guard had been removed", "evidence": ""},
            ],
            root_cause="no banksman",
            contributing_factors="wet floor",
            actor_id=11,
        )
        assert payload is not None
        assert payload["why_1"] == "the interlock was bypassed"
        assert payload["whys"][0]["evidence"] == "CCTV still 14:02"
        assert run.data["why_1"] == "the interlock was bypassed"
        assert run.data["why_2"] == "the guard had been removed"
        assert run.data["root_cause"] == "no banksman"
        for section in (ROOT_CAUSE_SECTION, LEGACY_RCA_SECTION):
            assert run.data["sections"][section]["why_1"] == "the interlock was bypassed"
            assert run.data["sections"][section]["root_cause"] == "no banksman"


@pytest.mark.asyncio
async def test_clearing_a_why_overwrites_the_stale_string(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"why_1": "the interlock was bypassed"})
        await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        payload = await InvestigationRcaService.upsert_workspace(
            db,
            investigation=run,
            tenant_id=TENANT,
            problem_statement="",
            whys=[{"level": 1, "answer": "", "evidence": ""}],
            root_cause="",
            contributing_factors="",
        )
        assert payload is not None
        assert payload["why_1"] == ""
        assert run.data["why_1"] == ""
        assert run.data["sections"][ROOT_CAUSE_SECTION]["why_1"] == ""


@pytest.mark.asyncio
async def test_a_write_converts_first_so_leftover_whys_are_not_lost(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"why_1": "the interlock was bypassed"})
        payload = await InvestigationRcaService.upsert_workspace(
            db,
            investigation=run,
            tenant_id=TENANT,
            problem_statement="",
            whys=[
                {"level": 1, "answer": "the interlock was bypassed", "evidence": ""},
                {"level": 2, "answer": "the guard had been removed", "evidence": ""},
            ],
            root_cause="",
            contributing_factors="",
        )
        assert payload is not None
        assert payload["why_1"] == "the interlock was bypassed"
        assert payload["why_2"] == "the guard had been removed"
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 1


@pytest.mark.asyncio
async def test_extra_why_levels_from_rca_tools_survive_a_workspace_save(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        db.add(
            FiveWhysAnalysis(
                tenant_id=TENANT,
                investigation_id=int(run.id),
                problem_statement="existing",
                whys=[
                    {"level": 1, "why": "", "answer": "one", "evidence": None},
                    {"level": 6, "why": "", "answer": "sixth", "evidence": "note"},
                ],
            )
        )
        await db.flush()
        payload = await InvestigationRcaService.upsert_workspace(
            db,
            investigation=run,
            tenant_id=TENANT,
            problem_statement="existing",
            whys=[{"level": 1, "answer": "one-edited", "evidence": ""}],
            root_cause="",
            contributing_factors="",
        )
        assert payload is not None
        levels = [item["level"] for item in payload["whys"]]
        assert 6 in levels
        sixth = next(item for item in payload["whys"] if item["level"] == 6)
        assert sixth["answer"] == "sixth"


# --------------------------------------------------------------------------- #
# Tenancy
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_another_tenants_analysis_is_invisible_even_with_the_right_run_id(session_factory):
    async with session_factory() as db:
        theirs = await _run(db, run_id=1, tenant_id=OTHER_TENANT)
        db.add(
            FiveWhysAnalysis(
                tenant_id=OTHER_TENANT,
                investigation_id=int(theirs.id),
                problem_statement="theirs",
                whys=[{"level": 1, "answer": "their why", "evidence": None}],
            )
        )
        await db.flush()

        ours = InvestigationRun(
            id=1,
            tenant_id=TENANT,
            template_id=1,
            assigned_entity_type="incident",
            assigned_entity_id=99,
            status="in_progress",
            title="ours",
            reference_number="INV-OURS",
            data={},
            version=1,
        )
        payload = await InvestigationRcaService.get_workspace(db, investigation=ours, tenant_id=TENANT)
        assert payload["analysis_id"] is None
        assert payload["why_1"] == ""

        refused = await InvestigationRcaService.upsert_workspace(
            db,
            investigation=theirs,
            tenant_id=TENANT,
            problem_statement="hijacked",
            whys=[{"level": 1, "answer": "hijacked", "evidence": ""}],
            root_cause="",
            contributing_factors="",
        )
        assert refused is None
        stored = await db.scalar(
            select(FiveWhysAnalysis.problem_statement).where(FiveWhysAnalysis.tenant_id == OTHER_TENANT)
        )
        assert stored == "theirs"


@pytest.mark.asyncio
async def test_mismatched_tenant_on_the_run_fails_closed(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"why_1": "the interlock was bypassed"})
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=OTHER_TENANT)
        assert payload["analysis_id"] is None
        assert payload["why_1"] == ""
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 0


@pytest.mark.asyncio
async def test_an_unscoped_analysis_for_this_run_is_claimed_not_duplicated(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        db.add(
            FiveWhysAnalysis(
                tenant_id=None,
                investigation_id=int(run.id),
                problem_statement="pre-C10",
                whys=[{"level": 1, "answer": "legacy tools row", "evidence": "photo"}],
            )
        )
        await db.flush()
        payload = await InvestigationRcaService.get_workspace(db, investigation=run, tenant_id=TENANT)
        assert payload["why_1"] == "legacy tools row"
        assert payload["whys"][0]["evidence"] == "photo"
        assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 1
        claimed = await db.scalar(select(FiveWhysAnalysis.tenant_id))
        assert claimed == TENANT
