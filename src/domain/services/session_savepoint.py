"""SAVEPOINT-scoped recovery for read paths that tolerate a failed sub-query.

Extracted from ``src/api/routes/actions.py`` (C-53) so the domain layer can use
the same recovery without importing the API layer, which the import-boundary
check forbids. The API route keeps its ``_read_savepoint`` name as an alias.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional


@dataclass
class SavepointScope:
    """Whether the scope actually put the transaction back into a usable state.

    ``recovered`` is only meaningful inside a caller's ``except``: it is True when
    a savepoint was opened *and* unwinding to it completed. A caller that cannot
    afford to leave an aborted transaction behind — the executive dashboard keeps
    querying after a failure — reads this to decide whether it still needs the
    blunter ``Session.rollback()``. A caller that is content to let one read fail
    on its own ignores it.
    """

    recovered: bool = False


@asynccontextmanager
async def read_savepoint(db: Any) -> AsyncIterator[SavepointScope]:
    """Scope one read so its failure cannot refuse every read after it.

    On PostgreSQL the first failing statement aborts the transaction and every
    later statement raises until the transaction is unwound, so an ``except`` that
    swallows the error without unwinding turns one broken action store into six.
    That is the C-8 shape.

    A SAVEPOINT is the unwind to use rather than ``Session.rollback()``: a full
    rollback expires every instance in the identity map, including the
    ``current_user`` authentication loaded on this same session, and a later lazy
    refresh of it over an async session raises MissingGreenlet — a 500 this
    repository has already paid for. Rolling back to a savepoint leaves clean
    instances alone.

    Sessions that cannot open a savepoint (test doubles, dialects without
    SAVEPOINT support) run the read unscoped, exactly as before, and report
    ``recovered=False`` so a caller that needs the transaction back can fall back.
    Mirrors ``_row_savepoint`` in the PAMS technician sync service.
    """
    scope = SavepointScope()
    begin_nested = getattr(db, "begin_nested", None)
    if begin_nested is None:
        yield scope
        return
    try:
        nested = begin_nested()
    except NotImplementedError:  # pragma: no cover - dialect without SAVEPOINT
        yield scope
        return

    from_body: Optional[BaseException] = None
    try:
        async with nested:
            try:
                yield scope
            except BaseException as exc:
                from_body = exc
                raise
    except BaseException as exc:
        # ``async with`` re-raises the body's own exception once it has rolled
        # back to the savepoint. A *different* exception leaving here is the
        # unwind itself failing, which leaves the transaction exactly as broken
        # as the body left it — so that must not be reported as recovered.
        if from_body is not None and exc is from_body:
            scope.recovered = True
        raise
