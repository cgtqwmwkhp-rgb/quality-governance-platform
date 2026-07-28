"""``GET /policy-acknowledgments/my-pending`` must not answer an absent table with ``[]``.

The residual half of C-23. The handler used to catch
:class:`~sqlalchemy.exc.ProgrammingError` and return ``{"items": [], "total": 0}``,
so a user whose acknowledgment table was missing was told they had nothing to
read. Unlike the dashboard, this endpoint has live consumers
(``PortalWork.tsx`` and ``MyReading.tsx``), and both defend with
``response.data.items ?? []``.

That idiom is why the honest signal here is a 503 and not an extra response
variant. A variant lacking ``items`` would be coerced straight back to "nothing
to read" by the ``?? []`` in both callers, reproducing the defect on the client
while the server congratulated itself. An error status cannot be coerced that
way: both pages already have a first-class error branch, so the truth arrives
without either page changing.

An empty list remains completely legitimate — it is what production returns
today, the table having no rows — so these tests pin both directions: an empty
read stays ``[]`` with 200, and an unreadable one is never expressible as ``[]``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.domain.error_codes import ErrorCode
from tests.integration._policy_ack_scratch import BACKING_TABLE, ScratchDatabase

MY_PENDING = "/api/v1/policy-acknowledgments/my-pending"


class TestTheHarnessCanSeeAMissingTable:
    """Without this, every assertion below could pass vacuously."""

    async def test_the_schema_starts_with_the_backing_table(self, ack_scratch: ScratchDatabase):
        assert await ack_scratch.has_backing_table() is True

    async def test_the_harness_really_lost_the_table(self, ack_scratch: ScratchDatabase):
        await ack_scratch.drop_backing_table()
        assert await ack_scratch.has_backing_table() is False, (
            "the scratch database still has the table, so this file cannot observe " "the condition it exists to test"
        )


class TestAReadThatHappened:
    """A list that was actually read keeps reporting exactly what it found."""

    async def test_pending_and_overdue_items_are_listed(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        await ack_scratch.seed_acknowledgments(("pending", "overdue", "completed"))

        response = await ack_scratch_client.get(MY_PENDING)

        assert response.status_code == 200, response.text
        body = response.json()
        # Completed work is not outstanding reading, so it is filtered out.
        assert body["total"] == 2
        assert {item["status"] for item in body["items"]} == {"pending", "overdue"}

    async def test_an_empty_queue_is_still_an_empty_list(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """Nothing to acknowledge is a real answer and must stay cheap to render.

        This is the state production is actually in — the table exists and holds
        no rows — so it has to keep working exactly as before. The fix narrows
        what ``[]`` is allowed to mean; it does not stop it meaning anything.
        """
        response = await ack_scratch_client.get(MY_PENDING)

        assert response.status_code == 200, response.text
        assert response.json() == {"items": [], "total": 0}


class TestAReadThatCouldNotHappen:
    """The defect: an absent table answered as an empty reading queue."""

    async def test_absent_table_is_not_a_success(self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient):
        await ack_scratch.drop_backing_table()
        assert await ack_scratch.has_backing_table() is False

        response = await ack_scratch_client.get(MY_PENDING)

        assert (
            response.status_code == 503
        ), f"an unreadable acknowledgment table answered {response.status_code}: {response.text}"

    async def test_no_empty_list_is_offered_when_nothing_was_read(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """The regression that matters: a payload a consumer could render as "all clear".

        ``items`` must be absent from the body entirely. Both live callers read
        ``response.data.items ?? []``, so an ``items`` key of any kind — empty,
        null, missing-from-a-200 — is indistinguishable from a clean inbox.
        """
        await ack_scratch.drop_backing_table()

        response = await ack_scratch_client.get(MY_PENDING)
        body = response.json()

        assert "items" not in body, f"unreadable response still offered an items list: {body!r}"
        assert "total" not in body, f"unreadable response still offered a total: {body!r}"

    async def test_the_absent_table_is_named_with_a_distinct_error_code(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """A generic 500 would not tell an operator which table to migrate."""
        await ack_scratch.drop_backing_table()

        body = (await ack_scratch_client.get(MY_PENDING)).json()

        assert body["error"]["code"] == ErrorCode.MEASUREMENT_UNAVAILABLE.value
        assert body["error"]["code"] == "MEASUREMENT_UNAVAILABLE"
        assert body["error"]["details"]["missing_tables"] == [BACKING_TABLE]
        assert BACKING_TABLE in body["error"]["message"]

    async def test_an_empty_queue_and_an_unreadable_one_are_not_interchangeable(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """The whole point: these two must not arrive as the same answer."""
        empty = await ack_scratch_client.get(MY_PENDING)
        await ack_scratch.drop_backing_table()
        unreadable = await ack_scratch_client.get(MY_PENDING)

        assert empty.status_code == 200
        assert unreadable.status_code == 503
        assert empty.json() != unreadable.json()
        assert empty.json()["items"] == []
        assert "items" not in unreadable.json()

    async def test_the_error_is_not_a_generic_server_fault(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """503, not 500: the request is fine and the code is not broken.

        The frontend classifies 502/503 as ``UNAVAILABLE`` rather than
        ``SERVER_ERROR``, which is the accurate category for schema lag.
        """
        await ack_scratch.drop_backing_table()

        response = await ack_scratch_client.get(MY_PENDING)

        assert response.status_code != 500
        assert response.status_code == 503
        assert response.json()["error"]["code"] != ErrorCode.INTERNAL_ERROR.value
