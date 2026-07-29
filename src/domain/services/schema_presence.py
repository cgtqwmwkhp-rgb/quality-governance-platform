"""Ask the database which tables it actually has, before reading them.

One implementation, because two would drift. ``PolicyAcknowledgmentService``
introduced this check in the policy-acknowledgment honesty work; document control
needs the identical question, and a second copy would be the third tool in this
repository to answer "does production have this table" differently from the other
two.

Why the question is asked before the query rather than after it fails
--------------------------------------------------------------------
1. **The exception type is dialect-dependent.** The same absent table raises
   ``ProgrammingError`` on PostgreSQL and ``OperationalError`` on SQLite, so an
   ``except ProgrammingError`` guard silently covers only one backend — and the
   test harnesses here run on both.
2. **On PostgreSQL the failure poisons the transaction.** A ``SELECT`` against a
   missing relation aborts the surrounding transaction, so every later statement
   in the same request — including an unrelated ``COMMIT`` of work that would
   have succeeded — fails with ``InFailedSqlTransaction``. Recovering after the
   fact means a rollback and a second round of work; asking first means the
   readable part of a request stays readable.
3. **Production and the models disagree by construction.** Production is built by
   Alembic; the models are the application's own idea of the schema; both CI
   harnesses build their schema with ``create_all``. A table with no create
   migration therefore exists in every test database and in no deployment, which
   is why this has to be a runtime question and cannot be a test-time one.
"""

from __future__ import annotations

from typing import Any, Iterable, Tuple

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession


async def absent_tables(db: AsyncSession, names: Iterable[str]) -> Tuple[str, ...]:
    """Which of ``names`` the connected database does not carry.

    Order follows ``names`` so a message listing them reads the same way twice.
    The inspector is built per call rather than cached: a cached "absent" would
    outlive the migration that fixes it, and this runs once per request.
    """
    wanted = tuple(names)
    if not wanted:
        return ()

    def _absent(sync_conn: Any) -> Tuple[str, ...]:
        inspector = sa_inspect(sync_conn)
        return tuple(name for name in wanted if not inspector.has_table(name))

    connection = await db.connection()
    return await connection.run_sync(_absent)
