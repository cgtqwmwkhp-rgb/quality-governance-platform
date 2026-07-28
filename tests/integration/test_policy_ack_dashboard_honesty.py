"""C-23 — ``GET /policy-acknowledgments/dashboard`` must not invent a measurement.

The handler used to catch :class:`~sqlalchemy.exc.ProgrammingError` and answer with
``completion_rate: 0.0``. To an auditor that reads as "nobody has acknowledged
anything", which is a statement of fact the system had not established. The two
outcomes are now distinct response variants and these tests pin the distinction.

The private database this relies on, and why the default harness cannot see an
absent table, are documented in ``tests/integration/_policy_ack_scratch``.
``test_the_harness_really_lost_the_table`` asserts the table is genuinely gone
before any assertion about the response is made.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from tests.integration._policy_ack_scratch import BACKING_TABLE, ScratchDatabase

DASHBOARD = "/api/v1/policy-acknowledgments/dashboard"


# --------------------------------------------------------------------------- #
#  The harness itself                                                          #
# --------------------------------------------------------------------------- #


class TestTheHarnessCanSeeAMissingTable:
    """Without this, every assertion below could pass vacuously."""

    async def test_the_schema_starts_with_the_backing_table(self, ack_scratch: ScratchDatabase):
        assert await ack_scratch.has_backing_table() is True

    async def test_the_harness_really_lost_the_table(self, ack_scratch: ScratchDatabase):
        await ack_scratch.drop_backing_table()
        assert await ack_scratch.has_backing_table() is False, (
            "the scratch database still has the table, so this file cannot observe " "the condition it exists to test"
        )

    async def test_a_query_against_the_dropped_table_really_fails(self, ack_scratch: ScratchDatabase):
        """The absence is a database fact, not a mocked exception."""
        await ack_scratch.drop_backing_table()
        with pytest.raises(sa.exc.SQLAlchemyError):
            async with ack_scratch.sessions() as session:
                await session.execute(sa.text(f"SELECT count(*) FROM {BACKING_TABLE}"))


# --------------------------------------------------------------------------- #
#  The contract                                                                #
# --------------------------------------------------------------------------- #


class TestMeasuredCompliance:
    """A real measurement still reports numbers, including a genuine zero."""

    async def test_counts_are_reported_when_the_table_is_there(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        await ack_scratch.seed_acknowledgments(("completed", "completed", "pending"))

        response = await ack_scratch_client.get(DASHBOARD)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["measurement"] == "measured"
        assert body["metrics"]["total_assignments"] == 3
        assert body["metrics"]["completed"] == 2
        assert body["metrics"]["completion_rate"] == pytest.approx(66.7)

    async def test_an_empty_table_is_a_measured_zero_not_an_unknown(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """Nothing assigned is a fact the system did establish, so it stays a number."""
        response = await ack_scratch_client.get(DASHBOARD)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["measurement"] == "measured"
        assert body["metrics"]["total_assignments"] == 0
        assert body["metrics"]["completion_rate"] == 0.0


class TestUnmeasurableCompliance:
    """The defect: an absent table answered as 0% compliance."""

    async def test_absent_table_is_reported_as_unmeasurable(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        await ack_scratch.drop_backing_table()
        assert await ack_scratch.has_backing_table() is False

        response = await ack_scratch_client.get(DASHBOARD)

        assert response.status_code == 200, response.text
        assert response.json()["measurement"] == "unmeasurable"

    async def test_no_number_is_offered_when_nothing_was_measured(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """The regression that matters: a rate a consumer could render as 0%."""
        await ack_scratch.drop_backing_table()
        assert await ack_scratch.has_backing_table() is False

        body = (await ack_scratch_client.get(DASHBOARD)).json()

        assert "metrics" not in body, (
            "an unmeasurable dashboard must not carry a metrics object at all; " f"got {body!r}"
        )
        leaked = [key for key, value in body.items() if isinstance(value, (int, float)) and not isinstance(value, bool)]
        assert leaked == [], f"unmeasurable response leaked numeric fields: {leaked}"

    async def test_the_absent_table_is_named(self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient):
        await ack_scratch.drop_backing_table()

        body = (await ack_scratch_client.get(DASHBOARD)).json()

        assert body["missing_tables"] == [BACKING_TABLE]
        assert BACKING_TABLE in body["reason"]

    async def test_the_two_states_are_not_interchangeable(
        self, ack_scratch: ScratchDatabase, ack_scratch_client: AsyncClient
    ):
        """A measured zero and an unknown must not serialise to the same payload."""
        measured = (await ack_scratch_client.get(DASHBOARD)).json()
        await ack_scratch.drop_backing_table()
        unmeasurable = (await ack_scratch_client.get(DASHBOARD)).json()

        assert measured["measurement"] == "measured"
        assert unmeasurable["measurement"] == "unmeasurable"
        assert measured != unmeasurable
        assert measured["metrics"]["completion_rate"] == 0.0
        assert "metrics" not in unmeasurable
