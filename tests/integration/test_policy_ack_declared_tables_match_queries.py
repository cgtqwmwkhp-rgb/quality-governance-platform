"""The declared table tuples must match the tables the queries actually read.

``PolicyAcknowledgmentService`` decides whether a figure is measurable by asking
whether the tables in ``COMPLIANCE_DASHBOARD_TABLES`` (or ``MY_PENDING_TABLES``)
exist. Nothing in the code ties those tuples to the queries the methods really
run, and that gap is the weak point of the preflight design:

    A count added over a second table would pass a preflight that does not name
    it, and then fail on the query — turning a condition the service is supposed
    to report cleanly back into a 500.

Both tuples currently hold one table and both methods read one table, so the
tuples are correct today. These tests exist so they cannot quietly stop being
correct. Rather than re-reading the source for ``select()`` calls, they execute
the methods against a real database and inspect the SQL that reaches the driver,
so a join introduced anywhere beneath them is caught.
"""

from __future__ import annotations

import re

import pytest
import sqlalchemy as sa

from src.domain.services.policy_acknowledgment import PolicyAcknowledgmentService
from tests.integration._policy_ack_scratch import ScratchDatabase

TENANT_ID = 1
USER_ID = 1


def _declared_table_names() -> set[str]:
    """Every table the app declares, used as the vocabulary to search SQL for.

    Looking only for names already known to be tables avoids parsing arbitrary
    SQL identifiers: aliases, CTEs and subquery labels are never mistaken for
    tables because they are not in this set.
    """
    import src.domain.models  # noqa: F401  — registers models on Base.metadata
    from src.infrastructure.database import Base

    return set(Base.metadata.tables.keys())


def _tables_read_by(sql: str, vocabulary: set[str]) -> set[str]:
    """Which declared tables this statement selects from or joins to.

    ``\\b`` on the trailing edge keeps ``policy_acknowledgments`` from matching
    ``FROM policy_acknowledgment_requirements``, since ``_`` is a word character.
    """
    found = set()
    for name in vocabulary:
        if re.search(rf'\b(?:from|join)\s+"?{re.escape(name)}"?\b', sql, re.IGNORECASE):
            found.add(name)
    return found


class _SqlRecorder:
    """Captures every statement the driver is asked to run."""

    def __init__(self, engine):
        self._sync_engine = engine.sync_engine
        self.statements: list[str] = []

    def _record(self, _conn, _cursor, statement, *_args):
        self.statements.append(statement)

    def __enter__(self) -> "_SqlRecorder":
        sa.event.listen(self._sync_engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *_exc) -> None:
        sa.event.remove(self._sync_engine, "before_cursor_execute", self._record)

    def tables_read(self, vocabulary: set[str]) -> set[str]:
        touched: set[str] = set()
        for statement in self.statements:
            touched |= _tables_read_by(statement, vocabulary)
        return touched


class TestTheDetectorWorks:
    """Guards against these tests passing because they see nothing at all."""

    async def test_a_statement_against_an_undeclared_table_is_noticed(self, ack_scratch: ScratchDatabase):
        """A control: the mechanism must report a table outside the declared tuple.

        Without this, a recorder that captured nothing — or an extractor that
        matched nothing — would make every assertion below vacuously true.
        """
        vocabulary = _declared_table_names()
        assert "policy_acknowledgment_requirements" in vocabulary

        with _SqlRecorder(ack_scratch.engine) as recorder:
            async with ack_scratch.sessions() as session:
                await session.execute(
                    sa.text(
                        "SELECT count(*) FROM policy_acknowledgments "
                        "JOIN policy_acknowledgment_requirements "
                        "ON policy_acknowledgment_requirements.id = policy_acknowledgments.requirement_id"
                    )
                )

        touched = recorder.tables_read(vocabulary)
        assert touched == {"policy_acknowledgments", "policy_acknowledgment_requirements"}
        # And it would be flagged, because the tuple does not name the second table.
        undeclared = touched - set(PolicyAcknowledgmentService.COMPLIANCE_DASHBOARD_TABLES)
        assert undeclared == {"policy_acknowledgment_requirements"}

    async def test_the_recorder_sees_something(self, ack_scratch: ScratchDatabase):
        with _SqlRecorder(ack_scratch.engine) as recorder:
            async with ack_scratch.sessions() as session:
                await session.execute(sa.text("SELECT 1"))
        assert recorder.statements, "the SQL recorder captured nothing, so it is not attached"


class TestDeclaredTablesCoverWhatIsRead:
    """The assertion that will fail the day a query outgrows its tuple."""

    async def test_dashboard_declares_every_table_it_aggregates(self, ack_scratch: ScratchDatabase):
        vocabulary = _declared_table_names()

        with _SqlRecorder(ack_scratch.engine) as recorder:
            async with ack_scratch.sessions() as session:
                result = await PolicyAcknowledgmentService(session).get_compliance_dashboard(tenant_id=TENANT_ID)

        assert recorder.statements, "no SQL was captured, so this proves nothing"
        touched = recorder.tables_read(vocabulary)
        assert touched, f"no declared table was recognised in {len(recorder.statements)} statements"

        undeclared = touched - set(PolicyAcknowledgmentService.COMPLIANCE_DASHBOARD_TABLES)
        assert undeclared == set(), (
            "get_compliance_dashboard reads tables that COMPLIANCE_DASHBOARD_TABLES "
            f"does not name: {sorted(undeclared)}. The preflight would report the "
            "dashboard measurable while one of these was absent, and the query would "
            "then fail — add them to the tuple."
        )
        # A measurement did happen, so the SQL captured is the real aggregation path.
        assert hasattr(result, "metrics")

    async def test_my_pending_declares_every_table_it_reads(self, ack_scratch: ScratchDatabase):
        vocabulary = _declared_table_names()

        with _SqlRecorder(ack_scratch.engine) as recorder:
            async with ack_scratch.sessions() as session:
                await PolicyAcknowledgmentService(session).get_user_pending_acknowledgments(
                    USER_ID,
                    tenant_id=TENANT_ID,
                )

        assert recorder.statements, "no SQL was captured, so this proves nothing"
        touched = recorder.tables_read(vocabulary)
        assert touched, f"no declared table was recognised in {len(recorder.statements)} statements"

        undeclared = touched - set(PolicyAcknowledgmentService.MY_PENDING_TABLES)
        assert undeclared == set(), (
            "get_user_pending_acknowledgments reads tables that MY_PENDING_TABLES "
            f"does not name: {sorted(undeclared)}. Absence of one of these would "
            "surface as a 500 instead of the 503 the endpoint promises."
        )

    @pytest.mark.parametrize(
        "tuple_name",
        ["COMPLIANCE_DASHBOARD_TABLES", "MY_PENDING_TABLES"],
    )
    def test_declared_tables_are_real_tables(self, tuple_name: str):
        """A typo in a tuple would make the preflight always find the table absent."""
        declared = set(getattr(PolicyAcknowledgmentService, tuple_name))
        assert declared, f"{tuple_name} is empty, so nothing would ever be checked"
        unknown = declared - _declared_table_names()
        assert unknown == set(), f"{tuple_name} names tables the app does not declare: {sorted(unknown)}"
