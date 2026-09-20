"""ICAM contributing factors: endpoints, storage, and the legacy dual-write (INV-C12).

The route functions are driven directly against a SQLite session — the idiom
INV-C7 findings and INV-C10 RCA tests use — with the tenancy helper patched.
The tenancy check itself is ``_get_investigation_or_404`` in ``investigations.py``.
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

from src.api.routes import investigation_factors as routes
from src.api.schemas.investigation_factor import (
    InvestigationFactorCreate,
    InvestigationFactorListResponse,
    InvestigationFactorResponse,
    InvestigationFactorUpdate,
)
from src.api.schemas.investigation_rca import InvestigationRcaUpsert
from src.domain.exceptions import AuthorizationError, NotFoundError
from src.domain.models.investigation import InvestigationRun
from src.domain.models.rca_tools import CausalDepth, FishboneCategory, FishboneDiagram, FiveWhysAnalysis
from src.domain.services.investigation_factors_service import (
    ICAM_CATEGORY_ORDER,
    InvestigationFactorsService,
    factor_line,
    read_factors,
)

try:
    from fastapi.routing import iter_route_contexts as _iter_route_contexts
except ImportError:

    def _iter_route_contexts(routes: Any) -> Any:
        return routes


REPO_ROOT = Path(__file__).resolve().parents[2]
TENANT = 7
OTHER_TENANT = 8
USER = SimpleNamespace(id=11, tenant_id=TENANT, is_superuser=False)
_PATH_CONVERTER = re.compile(r":(?:int|str|float|path|uuid)\}")

ORGANISATIONAL = FishboneCategory.ORGANISATIONAL.value
DEFENCES = FishboneCategory.ABSENT_FAILED_DEFENCES.value


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(FishboneDiagram.__table__.create)
        await conn.run_sync(FiveWhysAnalysis.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


async def _seed_run(db: AsyncSession, data=None, tenant_id: int = TENANT) -> InvestigationRun:
    run = InvestigationRun(
        id=7,
        tenant_id=tenant_id,
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


def _authorised(run):
    return patch.object(routes, "_get_investigation_or_404", new=AsyncMock(return_value=run))


def _create(
    category: str = ORGANISATIONAL,
    cause: str = "no refresher training schedule",
    sub_causes: list[str] | None = None,
    depth: str = "underlying",
) -> InvestigationFactorCreate:
    return InvestigationFactorCreate(
        category=category,
        cause=cause,
        sub_causes=sub_causes or [],
        depth=depth,
    )


# ---------------------------------------------------------------------------
# The taxonomy itself (DEC-1)
# ---------------------------------------------------------------------------


def test_the_categories_are_the_icam_four_and_not_the_6m_set():
    assert [category.value for category in FishboneCategory] == [
        "organisational_factors",
        "task_environmental_conditions",
        "individual_team_actions",
        "absent_failed_defences",
    ]
    assert [category.value for category in ICAM_CATEGORY_ORDER] == [category.value for category in FishboneCategory]


def test_causal_depth_is_the_three_hsg245_levels():
    assert [depth.value for depth in CausalDepth] == ["immediate", "underlying", "root"]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_run_with_no_factors_is_an_empty_list_not_a_404(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        payload = await routes.list_investigation_factors(7, db_session, USER)

    assert payload["items"] == []
    assert payload["total"] == 0
    assert payload["investigation_id"] == 7
    assert payload["diagram_id"] is None
    assert payload["contributing_factors_text"] == ""
    # The payload the client actually receives, not just the dict we built.
    assert InvestigationFactorListResponse.model_validate(payload).total == 0


@pytest.mark.asyncio
async def test_listing_does_not_create_a_diagram(db_session):
    """A read that writes would put an empty diagram on every run anyone opened."""
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.list_investigation_factors(7, db_session, USER)
    assert await db_session.scalar(select(func.count(FishboneDiagram.id))) == 0


@pytest.mark.asyncio
async def test_a_run_with_no_tenant_reads_as_empty_rather_than_500(db_session):
    await _seed_run(db_session)
    ghost = SimpleNamespace(id=7, tenant_id=None)
    with _authorised(ghost):
        payload = await routes.list_investigation_factors(7, db_session, USER)
    assert payload["items"] == []
    assert payload["unreadable_total"] == 0


# ---------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creating_a_factor_returns_every_field_the_request_sent(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        payload = await routes.create_investigation_factor(
            7,
            _create(sub_causes=["budget withdrawn", "no owner named"]),
            db_session,
            USER,
        )

    assert payload["total"] == 1
    stored = payload["items"][0]
    # Guard-1 shape, asserted by hand because the list envelope exempts this
    # endpoint from the static write-contract guard: every field the request
    # carried is readable back under the same name.
    assert stored["category"] == ORGANISATIONAL
    assert stored["cause"] == "no refresher training schedule"
    assert stored["sub_causes"] == ["budget withdrawn", "no owner named"]
    assert stored["depth"] == "underlying"
    assert stored["investigation_id"] == 7
    assert isinstance(stored["id"], int) and stored["id"] > 0
    assert payload["diagram_id"] is not None


@pytest.mark.asyncio
async def test_factors_are_stored_on_the_run_fishbone_diagram_not_a_new_table(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_factor(7, _create(), db_session, USER)

    diagram = (await db_session.execute(select(FishboneDiagram))).scalars().one()
    assert diagram.investigation_id == 7
    assert diagram.tenant_id == TENANT
    assert diagram.causes[ORGANISATIONAL][0]["cause"] == "no refresher training schedule"
    assert diagram.causes[ORGANISATIONAL][0]["depth"] == "underlying"


@pytest.mark.asyncio
async def test_the_diagram_effect_is_the_stated_problem_and_is_never_invented(session_factory):
    async with session_factory() as session:
        run = await _seed_run(session, data={"problem_statement": "fork lift struck a pedestrian"})
        with _authorised(run):
            await routes.create_investigation_factor(7, _create(), session, USER)
        diagram = (await session.execute(select(FishboneDiagram))).scalars().one()
        assert diagram.effect_statement == "fork lift struck a pedestrian"

    async with session_factory() as blank_session:
        run = InvestigationRun(
            id=8,
            tenant_id=TENANT,
            template_id=1,
            assigned_entity_type="incident",
            assigned_entity_id=43,
            status="in_progress",
            title="Second run",
            reference_number="INV-8",
            data={},
            version=1,
        )
        blank_session.add(run)
        await blank_session.commit()
        with _authorised(run):
            await routes.create_investigation_factor(8, _create(), blank_session, USER)
        diagram = (
            (await blank_session.execute(select(FishboneDiagram).where(FishboneDiagram.investigation_id == 8)))
            .scalars()
            .one()
        )
        # Not the run title standing in for an effect nobody wrote.
        assert diagram.effect_statement == ""


@pytest.mark.asyncio
async def test_two_factors_get_distinct_ids_that_survive_a_delete(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_factor(7, _create(cause="first"), db_session, USER)
        payload = await routes.create_investigation_factor(7, _create(cause="second"), db_session, USER)
        ids = [item["id"] for item in payload["items"]]
        assert len(set(ids)) == 2

        await routes.delete_investigation_factor(7, ids[1], db_session, USER)
        after = await routes.create_investigation_factor(7, _create(cause="third"), db_session, USER)

    # The deleted id is not handed out again: a stale editor holding it must not
    # silently start pointing at a different factor.
    assert ids[1] not in [item["id"] for item in after["items"]]


@pytest.mark.asyncio
async def test_creating_without_a_tenant_is_refused_and_stores_nothing(db_session):
    await _seed_run(db_session)
    ghost = SimpleNamespace(id=7, tenant_id=None)
    with _authorised(ghost):
        with pytest.raises(AuthorizationError):
            await routes.create_investigation_factor(7, _create(), db_session, USER)
    assert await db_session.scalar(select(func.count(FishboneDiagram.id))) == 0


@pytest.mark.asyncio
async def test_another_tenants_diagram_is_neither_read_nor_written(db_session):
    run = await _seed_run(db_session)
    db_session.add(
        FishboneDiagram(
            id=99,
            tenant_id=OTHER_TENANT,
            investigation_id=7,
            effect_statement="theirs",
            causes={ORGANISATIONAL: [{"id": 1, "cause": "another organisation's factor"}]},
        )
    )
    await db_session.commit()

    with _authorised(run):
        listed = await routes.list_investigation_factors(7, db_session, USER)
        await routes.create_investigation_factor(7, _create(cause="ours"), db_session, USER)

    assert listed["items"] == []
    theirs = await db_session.get(FishboneDiagram, 99)
    assert theirs.causes[ORGANISATIONAL][0]["cause"] == "another organisation's factor"
    assert await db_session.scalar(select(func.count(FishboneDiagram.id))) == 2


# ---------------------------------------------------------------------------
# Empty text is refused, not invented
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_empty_factor_text_is_refused_by_the_schema(blank):
    with pytest.raises(ValueError):
        InvestigationFactorCreate(category=ORGANISATIONAL, cause=blank, depth="root")


def test_a_factor_cannot_be_created_without_a_depth():
    """DEC-1 is ICAM crossed with HSG245 depth; a defaulted depth would be the
    server making the investigator's judgement for them."""
    with pytest.raises(ValueError):
        InvestigationFactorCreate(category=ORGANISATIONAL, cause="something real")


def test_an_unknown_category_is_refused_rather_than_stored():
    with pytest.raises(ValueError):
        InvestigationFactorCreate(category="manpower", cause="fatigue", depth="immediate")


def test_unknown_fields_are_forbidden_on_both_write_schemas():
    with pytest.raises(ValueError):
        InvestigationFactorCreate(
            category=ORGANISATIONAL, cause="real", depth="root", icam_level="no"  # type: ignore[call-arg]
        )
    with pytest.raises(ValueError):
        InvestigationFactorUpdate(icam_level="no")  # type: ignore[call-arg]


def test_an_update_naming_no_field_is_refused():
    with pytest.raises(ValueError):
        InvestigationFactorUpdate()


def test_every_writable_field_is_readable_back_under_the_same_name():
    """Guard 1 stated declaratively for this surface.

    ``tests/contract/test_write_contract_guards.py`` skips endpoints whose
    response is a list envelope, and both factor writers answer with the whole
    list — so the round-trip rule that caught PX-168 and the C11 ``assignee_*``
    mismatch is asserted here instead of being quietly unchecked. Renaming a
    request field without renaming the response field fails on this line, not in
    a client that cannot see whether its write landed.
    """
    writable = set(InvestigationFactorCreate.model_fields) | set(InvestigationFactorUpdate.model_fields)
    readable = set(InvestigationFactorResponse.model_fields)
    assert writable <= readable, f"not readable back: {sorted(writable - readable)}"


def test_blank_sub_causes_are_dropped_not_stored_as_empty_rows():
    model = _create(sub_causes=["  budget withdrawn ", "   ", ""])
    assert model.sub_causes == ["budget withdrawn"]


@pytest.mark.asyncio
async def test_the_service_refuses_blank_text_even_if_a_caller_bypasses_the_schema(db_session):
    run = await _seed_run(db_session)
    created = await InvestigationFactorsService.create_factor(
        db_session,
        investigation=run,
        tenant_id=TENANT,
        category=FishboneCategory.ORGANISATIONAL,
        cause="   ",
        depth=CausalDepth.ROOT,
    )
    assert created is None
    assert await db_session.scalar(select(func.count(FishboneDiagram.id))) == 0


# ---------------------------------------------------------------------------
# Updating and deleting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_updating_changes_only_what_was_named(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        created = await routes.create_investigation_factor(
            7, _create(sub_causes=["budget withdrawn"]), db_session, USER
        )
        factor_id = created["items"][0]["id"]
        payload = await routes.update_investigation_factor(
            7, factor_id, InvestigationFactorUpdate(cause="no refresher schedule at all"), db_session, USER
        )

    stored = payload["items"][0]
    assert stored["cause"] == "no refresher schedule at all"
    # Untouched by an edit that never mentioned them.
    assert stored["sub_causes"] == ["budget withdrawn"]
    assert stored["depth"] == "underlying"
    assert stored["id"] == factor_id


@pytest.mark.asyncio
async def test_moving_a_factor_between_categories_keeps_its_id(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        created = await routes.create_investigation_factor(7, _create(), db_session, USER)
        factor_id = created["items"][0]["id"]
        payload = await routes.update_investigation_factor(
            7,
            factor_id,
            InvestigationFactorUpdate(category=FishboneCategory.ABSENT_FAILED_DEFENCES),
            db_session,
            USER,
        )

    assert payload["total"] == 1
    assert payload["items"][0]["id"] == factor_id
    assert payload["items"][0]["category"] == DEFENCES
    diagram = (await db_session.execute(select(FishboneDiagram))).scalars().one()
    assert diagram.causes[ORGANISATIONAL] == []


@pytest.mark.asyncio
async def test_an_explicit_null_depth_clears_it_and_an_omitted_one_does_not(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        created = await routes.create_investigation_factor(7, _create(), db_session, USER)
        factor_id = created["items"][0]["id"]

        omitted = await routes.update_investigation_factor(
            7, factor_id, InvestigationFactorUpdate(cause="reworded"), db_session, USER
        )
        assert omitted["items"][0]["depth"] == "underlying"

        cleared = await routes.update_investigation_factor(
            7, factor_id, InvestigationFactorUpdate(depth=None, cause="reworded"), db_session, USER
        )

    assert cleared["items"][0]["depth"] is None
    # And the derived paragraph stops claiming a depth nobody recorded.
    assert "[" not in cleared["contributing_factors_text"]


@pytest.mark.asyncio
async def test_an_unknown_factor_id_is_a_404_on_update_and_delete(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_factor(7, _create(), db_session, USER)
        with pytest.raises(NotFoundError):
            await routes.update_investigation_factor(
                7, 4242, InvestigationFactorUpdate(cause="ghost"), db_session, USER
            )
        with pytest.raises(NotFoundError):
            await routes.delete_investigation_factor(7, 4242, db_session, USER)


@pytest.mark.asyncio
async def test_deleting_the_last_factor_leaves_a_valid_empty_list(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        created = await routes.create_investigation_factor(7, _create(), db_session, USER)
        payload = await routes.delete_investigation_factor(7, created["items"][0]["id"], db_session, USER)

    assert payload["items"] == []
    assert payload["contributing_factors_text"] == ""
    assert run.data["contributing_factors"] == ""


# ---------------------------------------------------------------------------
# Ordering and rendering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_factors_are_listed_in_icam_category_order_then_insertion_order(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_factor(
            7, _create(category=DEFENCES, cause="interlock bypassed", depth="immediate"), db_session, USER
        )
        await routes.create_investigation_factor(7, _create(cause="first organisational"), db_session, USER)
        payload = await routes.create_investigation_factor(7, _create(cause="second organisational"), db_session, USER)

    assert [item["cause"] for item in payload["items"]] == [
        "first organisational",
        "second organisational",
        "interlock bypassed",
    ]


def test_the_derived_line_states_category_sub_causes_and_depth():
    assert (
        factor_line(
            FishboneCategory.ORGANISATIONAL,
            "no refresher schedule",
            ["budget withdrawn", "no owner named"],
            CausalDepth.UNDERLYING,
        )
        == "Organisational factors: no refresher schedule (budget withdrawn; no owner named) [underlying cause]"
    )
    # No brackets and no parentheses for what was not recorded.
    assert (
        factor_line(FishboneCategory.INDIVIDUAL_TEAM, "banksman stood clear")
        == "Individual and team actions: banksman stood clear"
    )


# ---------------------------------------------------------------------------
# Dual-write to the readers that have not moved yet (until C18)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_legacy_contributing_factors_string_is_rewritten_flat_and_nested(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        payload = await routes.create_investigation_factor(7, _create(), db_session, USER)

    expected = "Organisational factors: no refresher training schedule [underlying cause]"
    assert payload["contributing_factors_text"] == expected
    assert run.data["contributing_factors"] == expected
    assert run.data["sections"]["section_4_root_cause"]["contributing_factors"] == expected
    assert run.data["sections"]["rca"]["contributing_factors"] == expected


@pytest.mark.asyncio
async def test_the_five_whys_analysis_list_is_kept_in_step_when_one_exists(db_session):
    run = await _seed_run(db_session)
    db_session.add(
        FiveWhysAnalysis(
            id=5,
            tenant_id=TENANT,
            investigation_id=7,
            problem_statement="fork lift struck a pedestrian",
            whys=[],
            contributing_factors=["a paragraph somebody typed"],
        )
    )
    await db_session.commit()

    with _authorised(run):
        await routes.create_investigation_factor(7, _create(), db_session, USER)
        await routes.create_investigation_factor(
            7, _create(category=DEFENCES, cause="interlock bypassed", depth="immediate"), db_session, USER
        )

    analysis = await db_session.get(FiveWhysAnalysis, 5)
    assert analysis.contributing_factors == [
        "Organisational factors: no refresher training schedule [underlying cause]",
        "Absent or failed defences: interlock bypassed [immediate cause]",
    ]


@pytest.mark.asyncio
async def test_no_five_whys_analysis_is_invented_just_to_mirror_a_factor(db_session):
    run = await _seed_run(db_session)
    with _authorised(run):
        await routes.create_investigation_factor(7, _create(), db_session, USER)
    assert await db_session.scalar(select(func.count(FiveWhysAnalysis.id))) == 0


@pytest.mark.asyncio
async def test_an_rca_save_that_omits_contributing_factors_does_not_clobber_them(db_session):
    """PX-168's shape: two writers for one field. After C12 the factor list is
    the author, so the workspace save leaves the derived paragraph alone."""
    from src.api.routes import investigation_rca as rca_routes

    run = await _seed_run(db_session)
    with _authorised(run):
        created = await routes.create_investigation_factor(7, _create(), db_session, USER)
    derived = created["contributing_factors_text"]

    body = InvestigationRcaUpsert(
        problem_statement="fork lift struck a pedestrian",
        whys=[{"level": 1, "answer": "the interlock was bypassed"}],
        root_cause="no banksman",
    )
    with patch.object(rca_routes, "_get_investigation_or_404", new=AsyncMock(return_value=run)):
        payload = await rca_routes.put_investigation_rca(7, body, db_session, USER)

    assert payload["contributing_factors"] == derived
    assert run.data["contributing_factors"] == derived

    with _authorised(run):
        listed = await routes.list_investigation_factors(7, db_session, USER)
    assert [item["cause"] for item in listed["items"]] == ["no refresher training schedule"]


# ---------------------------------------------------------------------------
# What this surface cannot present is reported, not dropped
# ---------------------------------------------------------------------------


def test_causes_under_a_pre_dec1_category_are_counted_not_re_categorised():
    snapshot = read_factors(
        {
            "manpower": [{"cause": "fatigue"}, {"cause": "training"}],
            ORGANISATIONAL: [{"id": 4, "cause": "no schedule", "depth": "root"}],
        },
        investigation_id=7,
    )
    assert [factor.cause for factor in snapshot.factors] == ["no schedule"]
    assert snapshot.unmapped_categories == ["manpower"]
    assert snapshot.unreadable_total == 2


def test_malformed_entries_are_counted_rather_than_shown_as_blank_factors():
    snapshot = read_factors(
        {ORGANISATIONAL: ["not an object", {"cause": "   "}, {"cause": "real"}]},
        investigation_id=7,
    )
    assert [factor.cause for factor in snapshot.factors] == ["real"]
    assert snapshot.unreadable_total == 2


def test_entries_without_an_id_read_the_same_way_twice():
    causes = {ORGANISATIONAL: [{"cause": "written by the generic fishbone route"}]}
    first = read_factors(causes, investigation_id=7)
    second = read_factors(causes, investigation_id=7)
    assert [factor.id for factor in first.factors] == [factor.id for factor in second.factors]
    assert first.factors[0].id > 0
    assert first.factors[0].depth is None


@pytest.mark.asyncio
async def test_a_mutation_never_drops_the_categories_it_does_not_understand(db_session):
    run = await _seed_run(db_session)
    db_session.add(
        FishboneDiagram(
            id=1,
            tenant_id=TENANT,
            investigation_id=7,
            effect_statement="",
            causes={"manpower": [{"cause": "fatigue"}], ORGANISATIONAL: []},
        )
    )
    await db_session.commit()

    with _authorised(run):
        payload = await routes.create_investigation_factor(7, _create(), db_session, USER)

    diagram = await db_session.get(FishboneDiagram, 1)
    assert diagram.causes["manpower"] == [{"cause": "fatigue"}]
    assert payload["unmapped_categories"] == ["manpower"]
    assert payload["unreadable_total"] == 1
    assert payload["total"] == 1


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_every_factor_endpoint_declares_a_permission():
    tree = ast.parse((REPO_ROOT / "src/api/routes/investigation_factors.py").read_text(encoding="utf-8"))
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
    assert len(decorated) == 4, "list, create, update, delete"
    for handler in decorated:
        assert "require_permission" in ast.dump(handler), f"{handler.name} is not permission-gated"


def test_the_factor_paths_are_mounted_where_the_client_calls_them():
    from src.main import app

    factors = {
        (method, _PATH_CONVERTER.sub("}", route.path))
        for route in _iter_route_contexts(app.routes)
        for method in getattr(route, "methods", set()) or set()
        if "/investigations/" in getattr(route, "path", "") and "/factors" in getattr(route, "path", "")
    }
    assert factors == {
        ("GET", "/api/v1/investigations/{investigation_id}/factors"),
        ("POST", "/api/v1/investigations/{investigation_id}/factors"),
        ("PATCH", "/api/v1/investigations/{investigation_id}/factors/{factor_id}"),
        ("DELETE", "/api/v1/investigations/{investigation_id}/factors/{factor_id}"),
    }
