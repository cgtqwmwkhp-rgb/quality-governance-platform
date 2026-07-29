"""A failed count must not empty the action register (C-53 residual).

#1426 stopped one drifted action store poisoning the other five counts. It left
two things alone, both because they change the response contract:

* ``_safe_scalar`` swallowed the failure and contributed ``0``, so the caller
  could not tell a store that holds nothing from a store it could not read;
* ``list_actions`` then short-circuited on ``total == 0`` and returned
  ``items: []`` **without querying for any rows at all**.

The visible consequence was an action register that rendered as empty, at HTTP
200, with no indication anything had failed — on a page whose entire purpose is
to show a director what is outstanding.

One correction to how that was framed, because it changes what needed fixing. The
short-circuit was described as suppressing rows that could have been read. It
cannot: a count names only the columns it filters on, ``select(IncidentAction)``
names every column, so any drift that breaks a store's count also breaks that
store's row read. Rows lost to a zero total were never readable in the first
place. What the short-circuit actually removed was the *opportunity to notice* —
it returned before the row reads that would have raised. Both halves still need
fixing, but the count's silence is the defect and the short-circuit is what kept
it quiet, rather than the other way round.

``TestACountedRowThatCannotBeListed`` below records the reverse asymmetry, which
is worse and which no amount of short-circuit reasoning reaches: a count that
succeeds while the row read fails, producing ``total: 3`` beside an empty list.

Every test here runs against its own PostgreSQL database with a column genuinely
dropped, because neither property is reproducible on the shared integration
schema: ``create_all`` runs before each test there, so the schema always matches
the models and these tests would pass whether or not the defect were fixed. See
``tests/integration/_fabricated_zero_scratch`` for why real DDL rather than a
monkeypatched raise, and why PostgreSQL specifically.

Observed before the fix, on the drifted database (2 CAPA + 3 incident actions
seeded, ``capa_actions.tenant_id`` dropped):

    total ............ 3       true value: 5
    items returned ... 3
    sources_complete . <field absent>

and with only the 2 CAPA actions seeded:

    total ............ 0       true value: 2
    items returned ... 0

The second case is the dangerous one. Both are asserted below.
"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from tests.integration._fabricated_zero_scratch import (
    CAPA_ACTIONS_TENANT,
    INCIDENT_ACTIONS_DESCRIPTION,
    is_postgres,
)

ACTIONS = "/api/v1/actions/"

pytestmark = pytest.mark.skipif(
    not is_postgres(os.environ.get("DATABASE_URL", "")),
    reason=(
        "the drift under test depends on DROP COLUMN aborting the surrounding "
        "transaction, which SQLite does not do. Set DATABASE_URL to PostgreSQL (CI does)."
    ),
)


async def _list(client: AsyncClient) -> dict:
    response = await client.get(ACTIONS)
    assert response.status_code == 200, response.text
    return response.json()


class TestAnUnreadableStoreIsNotAnEmptyRegister:
    """The headline defect: rows present, register renders empty, nothing says so."""

    @pytest.mark.asyncio
    async def test_rows_exist_but_only_the_broken_store_holds_them(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """The exact shape that produced a blank page at HTTP 200.

        Two CAPA actions exist. The only store that holds any action is the one
        whose ``tenant_id`` is gone, so every count fails and ``total`` is 0.
        Pre-fix that zero reached the short-circuit and the endpoint returned an
        empty register; the assertion that bites is ``sources_complete is False``,
        which pre-fix was an absent field and so read as a complete, empty
        register to any client.
        """
        await drifted_scratch.seed_capa_actions(2)
        await drifted_scratch.drop_column(*CAPA_ACTIONS_TENANT)
        assert not await drifted_scratch.has_column(*CAPA_ACTIONS_TENANT), "the drift did not take"

        body = await _list(drifted_scratch_client)

        assert body["sources_complete"] is False, "an unreadable store must not report a complete register"
        assert body["unavailable_sources"] == ["capa"]

    @pytest.mark.asyncio
    async def test_an_empty_register_still_reports_itself_complete(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """The other half of the distinction, and the reason a flag is needed.

        A tenant with no actions is a real, common, correct empty register. The
        fix narrows what an empty ``items`` may mean; it must not make every
        empty register look broken, or the warning becomes noise and gets ignored.
        """
        body = await _list(drifted_scratch_client)

        assert body["items"] == []
        assert body["total"] == 0
        assert body["sources_complete"] is True
        assert body["unavailable_sources"] == []

    @pytest.mark.asyncio
    async def test_the_two_empty_registers_are_distinguishable(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """Stated as one assertion because it is the whole defect class.

        Before the fix these two responses were byte-identical. That is what
        "absence rendering as health" means here: the API had no way to express
        the difference, so no client could render it.
        """
        genuinely_empty = await _list(drifted_scratch_client)

        await drifted_scratch.seed_capa_actions(2)
        await drifted_scratch.drop_column(*CAPA_ACTIONS_TENANT)
        unreadable = await _list(drifted_scratch_client)

        assert genuinely_empty["items"] == unreadable["items"] == []
        assert genuinely_empty["total"] == unreadable["total"] == 0
        assert genuinely_empty != unreadable, "a broken register must not be expressible as an empty one"


class TestReadableRowsSurviveABrokenStore:
    """Degrade to partial, not to blank."""

    @pytest.mark.asyncio
    async def test_the_healthy_stores_rows_are_still_returned(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """Three incident actions are readable; a broken CAPA store must not cost them.

        This is the assertion that catches a naive fix. Turning the failure into a
        503, or letting the aborted transaction stand, would lose these three rows
        too — trading a silent wrong answer for no answer.
        """
        await drifted_scratch.seed_capa_actions(2)
        await drifted_scratch.seed_incident_actions(3)
        await drifted_scratch.drop_column(*CAPA_ACTIONS_TENANT)

        body = await _list(drifted_scratch_client)

        assert len(body["items"]) == 3, f"readable incident actions were dropped: {body!r}"
        assert {item["source_type"] for item in body["items"]} == {"incident"}
        assert body["sources_complete"] is False
        assert body["unavailable_sources"] == ["capa"]

    @pytest.mark.asyncio
    async def test_a_broken_row_read_does_not_poison_the_read_after_it(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """The row reads needed savepoint scoping too, not just the counts.

        #1426 wrapped the six *counts* in ``_read_savepoint`` and left the six *row*
        reads bare. On PostgreSQL a failed statement aborts the transaction, so
        every row read after the failing one is refused whether or not its own
        table is healthy.

        Read order is incident, rta, complaint, investigation, capa, capa_item, so
        this needs the healthy rows to sit in ``capa_items`` — *after* the broken
        ``capa_actions`` — to observe anything. Putting them in ``incident_actions``
        would prove nothing, because incidents are read first and would survive on
        the unfixed code too.
        """
        await drifted_scratch.seed_capa_actions(2)
        await drifted_scratch.seed_capa_items(2)
        await drifted_scratch.drop_column(*CAPA_ACTIONS_TENANT)

        body = await _list(drifted_scratch_client)

        assert len(body["items"]) == 2, "the aborted transaction swallowed the healthy read after the failure"
        # Keyed on action_key, not source_type: `_capa_item_to_response` reports
        # source_type "investigation" for every CAPA plan item (pre-existing, and
        # unrelated to this change), so source_type cannot identify the store here.
        assert all(item["action_key"].startswith("capa_item:") for item in body["items"])
        assert body["unavailable_sources"] == ["capa"], "only the genuinely broken store may be named"

    @pytest.mark.asyncio
    async def test_total_is_a_floor_and_says_so(self, drifted_scratch, drifted_scratch_client: AsyncClient) -> None:
        """5 actions exist, 3 are countable. Reporting 3 is defensible; reporting it as *the* total is not."""
        await drifted_scratch.seed_capa_actions(2)
        await drifted_scratch.seed_incident_actions(3)
        await drifted_scratch.drop_column(*CAPA_ACTIONS_TENANT)

        body = await _list(drifted_scratch_client)

        assert body["total"] == 3
        assert body["sources_complete"] is False, "a partial total must not be published as complete"


class TestACountedRowThatCannotBeListed:
    """The worst state the register can reach, and the short-circuit is not why.

    Measured, not reasoned: with ``incident_actions.description`` dropped and three
    rows seeded, ``origin/main`` answered

        HTTP 200, total: 3, items returned: 0, sources_complete: <absent>

    A register asserting three outstanding actions and displaying none, with
    nothing marking it as degraded. The zero-total short-circuit is not implicated
    — ``total`` is 3, so it never fires. The cause is an unguarded row read.

    This corrects the brief, which attributed the empty register to the
    short-circuit suppressing readable rows. It cannot do that: a count names only
    the filter columns, ``select(IncidentAction)`` names all of them, so any drift
    that breaks a count breaks that store's row read too. The rows a zero total
    "suppressed" were never readable. What the short-circuit actually cost was the
    *chance to notice* — it returned before the row reads that would have failed
    loudly.
    """

    @pytest.mark.asyncio
    async def test_a_count_without_a_listable_row_is_marked_incomplete(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        await drifted_scratch.seed_incident_actions(3)
        await drifted_scratch.drop_column(*INCIDENT_ACTIONS_DESCRIPTION)

        body = await _list(drifted_scratch_client)

        assert body["total"] == 3, "the count still succeeds — that is what makes this shape possible"
        assert body["items"] == []
        assert body["sources_complete"] is False, "a total with no listable row must not look healthy"
        assert body["unavailable_sources"] == ["incident"]

    @pytest.mark.asyncio
    async def test_pagination_still_answers_beyond_the_last_page(self, drifted_scratch_client: AsyncClient) -> None:
        """The short-circuit also served page-past-the-end; removing it must not break that."""
        response = await drifted_scratch_client.get(ACTIONS, params={"page": 9, "page_size": 10})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["items"] == []
        assert body["page"] == 9
        assert body["sources_complete"] is True
