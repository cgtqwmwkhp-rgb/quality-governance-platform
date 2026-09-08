"""Findings are rows, and the legacy paragraph still reads correctly (INV-C7).

SQLite-backed: only ``investigation_runs`` and ``investigation_findings`` are
created, which is enough because SQLite does not enforce the FK targets these
tables carry (tenants, users, investigation_templates). The same shape the
AUD-F5 and audit-challenge service tests use.

What is being defended here, in order of what would hurt most if it broke:

* a conversion that runs twice would duplicate every finding on every page load;
* a tenant filter that only exists on the parent lookup would let a crafted id
  reach another organisation's finding;
* a ``findings`` string that stops tracking the rows would let INV-C8's closure
  gate — which still reads the string — pass or block on text nobody can see.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.investigation import InvestigationRun
from src.domain.models.investigation_finding import InvestigationFinding
from src.domain.services.investigation_findings_service import (
    InvestigationFindingsService,
    join_findings_bodies,
    split_legacy_findings,
    sync_findings_text,
)

TENANT = 7
OTHER_TENANT = 9
FINDINGS_SECTION = "section_3_investigation_findings"


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(InvestigationFinding.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def _run(db: AsyncSession, *, run_id: int = 1, tenant_id: int = TENANT, data=None) -> InvestigationRun:
    run = InvestigationRun(
        id=run_id,
        tenant_id=tenant_id,
        template_id=1,
        assigned_entity_type="incident",
        # One investigation per source record per tenant (uq_investigation_runs_tenant_source),
        # so each fixture run needs its own source id.
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


def _bodies(rows) -> list[str]:
    return [row.body for row in rows]


# --------------------------------------------------------------------------- #
# The split rule — the only place legacy text becomes structure
# --------------------------------------------------------------------------- #


def test_numbered_lines_become_one_finding_each():
    rows = split_legacy_findings("1. Guard was removed\n2) Interlock bypassed\n(3) No banksman")
    assert rows == ["Guard was removed", "Interlock bypassed", "No banksman"]


def test_a_wrapped_numbered_finding_is_not_torn_in_two():
    """A continuation line carries no marker, so it belongs to the finding above it."""
    rows = split_legacy_findings("1. Guard was removed\n   before the shift started\n2. Interlock bypassed")
    assert rows == ["Guard was removed\n   before the shift started", "Interlock bypassed"]


def test_text_before_the_first_marker_is_kept_as_its_own_finding():
    rows = split_legacy_findings("Site was wet.\n1. Guard was removed")
    assert rows == ["Site was wet.", "Guard was removed"]


def test_bullets_count_as_markers():
    assert split_legacy_findings("- one\n* two\n\u2022 three") == ["one", "two", "three"]


def test_plain_newlines_become_one_finding_each():
    assert split_legacy_findings("Guard was removed\nInterlock bypassed") == [
        "Guard was removed",
        "Interlock bypassed",
    ]


def test_blank_lines_split_paragraphs_rather_than_lines():
    """A two-line paragraph is one finding. Splitting it would invent a second."""
    rows = split_legacy_findings("Guard was removed\nbefore the shift.\n\nNo banksman was present.")
    assert rows == ["Guard was removed\nbefore the shift.", "No banksman was present."]


def test_a_date_is_not_a_list_marker():
    assert split_legacy_findings("2026-03-01 the guard was removed") == ["2026-03-01 the guard was removed"]


@pytest.mark.parametrize("value", ["", "   ", "\n\n", None, 42, ["already", "rows"]])
def test_nothing_is_invented_from_an_empty_or_non_string_value(value):
    assert split_legacy_findings(value) == []


def test_join_leaves_a_single_finding_exactly_as_typed():
    """The common legacy shape is one paragraph; numbering it would rewrite the pack."""
    assert join_findings_bodies(["Guard was removed"]) == "Guard was removed"


def test_join_numbers_a_real_list_and_survives_a_round_trip():
    text = join_findings_bodies(["Guard was removed", "No banksman\nwas present"])
    assert text == "1. Guard was removed\n2. No banksman\nwas present"
    assert split_legacy_findings(text) == ["Guard was removed", "No banksman\nwas present"]


def test_join_of_nothing_is_empty_not_a_placeholder():
    assert join_findings_bodies([]) == ""
    assert join_findings_bodies(["", "  "]) == ""


# --------------------------------------------------------------------------- #
# The JSON sync — what INV-C8's gate and the pack keep reading
# --------------------------------------------------------------------------- #


def test_sync_writes_the_flat_key_and_the_nested_section():
    out = sync_findings_text({}, "1. one\n2. two")
    assert out["findings"] == "1. one\n2. two"
    assert out["sections"][FINDINGS_SECTION]["findings"] == "1. one\n2. two"


def test_sync_overwrites_a_stale_nested_value():
    """The C4 merge only fills blanks; a derived value has to replace both shapes."""
    out = sync_findings_text(
        {"findings": "old flat", "sections": {FINDINGS_SECTION: {"findings": "old nested", "conclusion": "keep"}}},
        "new text",
    )
    assert out["findings"] == "new text"
    assert out["sections"][FINDINGS_SECTION]["findings"] == "new text"
    assert out["sections"][FINDINGS_SECTION]["conclusion"] == "keep"


def test_sync_carries_unrelated_data_over_and_does_not_mutate_the_input():
    original = {
        "source_snapshot": {"reference_number": "RTA-42"},
        "sections": {"section_1_details": {"location": "yard"}},
    }
    out = sync_findings_text(original, "text")
    assert out["source_snapshot"] == {"reference_number": "RTA-42"}
    assert out["sections"]["section_1_details"] == {"location": "yard"}
    assert "findings" not in original
    assert original["sections"] == {"section_1_details": {"location": "yard"}}


def test_sync_preserves_a_list_shaped_sections_payload():
    """Rewriting a list into a dict would change what the closure walk can see."""
    out = sync_findings_text({"sections": [{"id": FINDINGS_SECTION, "fields": {"conclusion": "c"}}]}, "text")
    assert isinstance(out["sections"], list)
    assert out["sections"][0]["fields"] == {"conclusion": "c", "findings": "text"}


def test_sync_never_overwrites_a_structured_nested_answer():
    out = sync_findings_text({"sections": {FINDINGS_SECTION: {"findings": ["a", "b"]}}}, "text")
    assert out["sections"][FINDINGS_SECTION]["findings"] == ["a", "b"]
    assert out["findings"] == "text"


def test_sync_freezes_a_sections_value_that_is_not_readable_as_sections():
    out = sync_findings_text({"sections": "corrupt"}, "text")
    assert out["sections"] == "corrupt"
    assert out["findings"] == "text"


def test_sync_returns_a_non_dict_payload_unchanged():
    assert sync_findings_text(None, "text") is None
    assert sync_findings_text("not json", "text") == "not json"


def test_sync_clears_both_shapes_when_every_finding_is_gone():
    out = sync_findings_text({"findings": "old", "sections": {FINDINGS_SECTION: {"findings": "old"}}}, "")
    assert out["findings"] == ""
    assert out["sections"][FINDINGS_SECTION]["findings"] == ""


def test_sync_does_not_create_a_section_just_to_hold_an_empty_string():
    out = sync_findings_text({"sections": {}}, "")
    assert out["sections"] == {}


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_an_investigation_with_no_findings_lists_empty_rather_than_failing(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert rows == []
        assert run.data == {}


@pytest.mark.asyncio
async def test_create_appends_in_order_and_syncs_the_string(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        for body in ("Guard was removed", "No banksman present"):
            await InvestigationFindingsService.create_finding(
                db, investigation=run, tenant_id=TENANT, body=body, actor_id=11
            )

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["Guard was removed", "No banksman present"]
        assert [row.sort_order for row in rows] == [0, 1]
        assert [row.created_by_id for row in rows] == [11, 11]
        assert run.data["findings"] == "1. Guard was removed\n2. No banksman present"
        assert run.data["sections"][FINDINGS_SECTION]["findings"] == run.data["findings"]


@pytest.mark.asyncio
async def test_update_rewrites_one_body_and_leaves_the_order_alone(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        first = await InvestigationFindingsService.create_finding(db, investigation=run, tenant_id=TENANT, body="typo")
        await InvestigationFindingsService.create_finding(db, investigation=run, tenant_id=TENANT, body="second")

        updated = await InvestigationFindingsService.update_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=first.id, body="Guard was removed", actor_id=11
        )
        assert updated is not None and updated.sort_order == 0

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["Guard was removed", "second"]
        assert run.data["findings"] == "1. Guard was removed\n2. second"


@pytest.mark.asyncio
async def test_reorder_applies_the_requested_order(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        created = [
            await InvestigationFindingsService.create_finding(db, investigation=run, tenant_id=TENANT, body=body)
            for body in ("one", "two", "three")
        ]

        reordered = await InvestigationFindingsService.reorder_findings(
            db,
            investigation=run,
            tenant_id=TENANT,
            finding_ids=[created[2].id, created[0].id, created[1].id],
        )
        assert reordered is not None
        assert _bodies(reordered) == ["three", "one", "two"]

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["three", "one", "two"]
        assert [row.sort_order for row in rows] == [0, 1, 2]
        assert run.data["findings"] == "1. three\n2. one\n3. two"


@pytest.mark.asyncio
async def test_reorder_refuses_a_list_that_is_not_exactly_this_runs_findings(session_factory):
    """A stale editor omitting an id must not silently drop that finding's place."""
    async with session_factory() as db:
        run = await _run(db)
        created = [
            await InvestigationFindingsService.create_finding(db, investigation=run, tenant_id=TENANT, body=body)
            for body in ("one", "two")
        ]

        assert (
            await InvestigationFindingsService.reorder_findings(
                db, investigation=run, tenant_id=TENANT, finding_ids=[created[0].id]
            )
            is None
        )
        assert (
            await InvestigationFindingsService.reorder_findings(
                db, investigation=run, tenant_id=TENANT, finding_ids=[created[0].id, created[0].id]
            )
            is None
        )
        assert (
            await InvestigationFindingsService.reorder_findings(
                db, investigation=run, tenant_id=TENANT, finding_ids=[created[0].id, created[1].id, 9999]
            )
            is None
        )

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["one", "two"]


@pytest.mark.asyncio
async def test_delete_closes_the_gap_in_sort_order(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        created = [
            await InvestigationFindingsService.create_finding(db, investigation=run, tenant_id=TENANT, body=body)
            for body in ("one", "two", "three")
        ]

        assert await InvestigationFindingsService.delete_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=created[0].id
        )

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["two", "three"]
        assert [row.sort_order for row in rows] == [0, 1]

        # A later append lands after them rather than colliding with the freed slot.
        await InvestigationFindingsService.create_finding(db, investigation=run, tenant_id=TENANT, body="four")
        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["two", "three", "four"]


@pytest.mark.asyncio
async def test_deleting_the_last_finding_empties_the_string_and_does_not_resurrect_it(session_factory):
    """The failure this guards: an emptied list re-converting from its own stale text."""
    async with session_factory() as db:
        run = await _run(db, data={"findings": "Guard was removed"})

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["Guard was removed"]

        assert await InvestigationFindingsService.delete_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=rows[0].id
        )
        assert run.data["findings"] == ""

        assert await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT) == []


@pytest.mark.asyncio
async def test_deleting_a_finding_that_is_not_this_runs_reports_missing(session_factory):
    async with session_factory() as db:
        run = await _run(db)
        other = await _run(db, run_id=2)
        stray = await InvestigationFindingsService.create_finding(
            db, investigation=other, tenant_id=TENANT, body="belongs to run 2"
        )

        assert not await InvestigationFindingsService.delete_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=stray.id
        )
        assert not await InvestigationFindingsService.delete_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=9999
        )
        assert (
            await InvestigationFindingsService.update_finding(
                db, investigation=run, tenant_id=TENANT, finding_id=stray.id, body="hijacked"
            )
            is None
        )
        assert stray.body == "belongs to run 2"


# --------------------------------------------------------------------------- #
# Legacy conversion
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_legacy_numbered_string_converts_on_first_list(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"findings": "1. Guard was removed\n2. No banksman present"})

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["Guard was removed", "No banksman present"]
        assert run.data["findings"] == "1. Guard was removed\n2. No banksman present"


@pytest.mark.asyncio
async def test_a_nested_only_legacy_string_converts_too(session_factory):
    """INV-C4 writes both shapes, but a run created from a record may only be nested."""
    async with session_factory() as db:
        run = await _run(db, data={"sections": {FINDINGS_SECTION: {"findings": "Guard was removed"}}})

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["Guard was removed"]
        assert run.data["findings"] == "Guard was removed"


@pytest.mark.asyncio
async def test_conversion_does_not_repeat_on_every_read(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"findings": "Guard was removed\nNo banksman present"})

        for _ in range(3):
            rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)

        assert _bodies(rows) == ["Guard was removed", "No banksman present"]
        total = await db.scalar(select(func.count(InvestigationFinding.id)))
        assert total == 2


@pytest.mark.asyncio
async def test_conversion_does_not_repeat_after_an_edit_changes_the_string(session_factory):
    """The guard is "zero rows", not "the string looks unconverted"."""
    async with session_factory() as db:
        run = await _run(db, data={"findings": "Guard was removed"})
        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)

        await InvestigationFindingsService.update_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=rows[0].id, body="Guard was removed before the shift"
        )
        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)

        assert _bodies(rows) == ["Guard was removed before the shift"]
        assert await db.scalar(select(func.count(InvestigationFinding.id))) == 1


@pytest.mark.asyncio
async def test_an_empty_legacy_string_produces_no_rows(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"findings": "   ", "conclusion": "unsafe system of work"})

        assert await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT) == []
        # Nothing was written back: an untouched blob comes back untouched.
        assert run.data == {"findings": "   ", "conclusion": "unsafe system of work"}


@pytest.mark.asyncio
async def test_a_write_converts_first_so_the_legacy_paragraph_is_not_lost(session_factory):
    """Adding a finding to an unconverted run must not orphan what was already typed."""
    async with session_factory() as db:
        run = await _run(db, data={"findings": "Guard was removed"})

        await InvestigationFindingsService.create_finding(
            db, investigation=run, tenant_id=TENANT, body="No banksman present"
        )

        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        assert _bodies(rows) == ["Guard was removed", "No banksman present"]


# --------------------------------------------------------------------------- #
# Tenancy
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_another_tenants_findings_are_invisible_even_with_the_right_run_id(session_factory):
    async with session_factory() as db:
        theirs = await _run(db, run_id=1, tenant_id=OTHER_TENANT)
        await InvestigationFindingsService.create_finding(
            db, investigation=theirs, tenant_id=OTHER_TENANT, body="their finding"
        )

        # Same run object, our tenant id: the row filter refuses independently of
        # whatever the caller managed to load.
        assert (
            await InvestigationFindingsService._ordered_rows(db, investigation_id=1, tenant_id=TENANT)  # noqa: SLF001
            == []
        )
        assert (
            await InvestigationFindingsService.update_finding(
                db, investigation=theirs, tenant_id=TENANT, finding_id=1, body="hijacked"
            )
            is None
        )
        assert not await InvestigationFindingsService.delete_finding(
            db, investigation=theirs, tenant_id=TENANT, finding_id=1
        )
        assert (
            await InvestigationFindingsService.reorder_findings(
                db, investigation=theirs, tenant_id=TENANT, finding_ids=[1]
            )
            is None
        )


@pytest.mark.asyncio
async def test_conversion_is_per_tenant_and_does_not_see_across(session_factory):
    """Two tenants' runs share an id in this fixture; neither may convert the other's."""
    async with session_factory() as db:
        ours = await _run(db, run_id=1, tenant_id=TENANT, data={"findings": "ours"})
        theirs = await _run(db, run_id=2, tenant_id=OTHER_TENANT, data={"findings": "theirs"})

        await InvestigationFindingsService.list_findings(db, investigation=ours, tenant_id=TENANT)
        await InvestigationFindingsService.list_findings(db, investigation=theirs, tenant_id=OTHER_TENANT)

        our_rows = await InvestigationFindingsService.list_findings(db, investigation=ours, tenant_id=TENANT)
        their_rows = await InvestigationFindingsService.list_findings(db, investigation=theirs, tenant_id=OTHER_TENANT)
        assert _bodies(our_rows) == ["ours"]
        assert _bodies(their_rows) == ["theirs"]
        assert {row.tenant_id for row in our_rows} == {TENANT}
