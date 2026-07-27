"""Refuse to run tests against a database that is not local and disposable.

The integration harness reads ``DATABASE_URL`` from the environment with
``os.environ.setdefault``, so a value already exported in the shell is used
verbatim. It then calls ``Base.metadata.create_all`` and seeds a default tenant
and user id=1 before every test. Point that at a real deployment and the suite
writes to it: creating tables Alembic did not put there, inserting seed rows,
and then running every test's own writes against live data.

That very nearly happened during the Run021 verification work, where
``DATABASE_URL`` was still exported from a read-only production session. Nothing
was written, but only because the production firewall had already been closed —
which is luck, not a control. Hence this guard.

The check is host-based rather than name-based on purpose: a deny-list of things
that look like production only catches the deployments someone thought of, while
an allow-list of local hosts catches everything else by default.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

# Hosts a disposable test database can legitimately live on: the developer's own
# machine, and the service names used by docker-compose and the CI Postgres
# service container. CI itself only ever uses sqlite or localhost:5432.
_LOCAL_HOSTS = frozenset({"", "localhost", "127.0.0.1", "::1", "db", "postgres", "postgres-test"})

# Set this only when you have deliberately pointed the suite at a throwaway
# remote database and understand it will be written to and seeded.
_OVERRIDE_ENV = "QGP_I_UNDERSTAND_TESTS_WILL_WRITE_TO_THIS_DATABASE"


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when the configured test DSN is not local and disposable."""


def _host_of(dsn: str) -> str:
    # urlsplit chokes on the '+driver' in 'postgresql+asyncpg://', so strip it.
    scheme, _, rest = dsn.partition("://")
    base_scheme = scheme.split("+", 1)[0]
    try:
        return (urlsplit(f"{base_scheme}://{rest}").hostname or "").lower()
    except ValueError:
        # An unparseable DSN is not demonstrably local, so treat it as unsafe
        # rather than letting it through on a technicality.
        return "<unparseable>"


def assert_test_database_is_local(dsn: str | None = None) -> None:
    """Abort the test session unless the DSN is local and disposable.

    SQLite is always allowed: it is a file, and the harness owns it. Anything
    else must resolve to a host on the allow-list. Silence is the failure mode
    being defended against here, so this raises rather than warns.
    """
    if os.environ.get(_OVERRIDE_ENV) == "1":
        print(
            f"WARNING: {_OVERRIDE_ENV}=1 — the test database safety guard is disabled. "
            "This suite creates tables and seeds rows; make sure this database is disposable.",
            file=sys.stderr,
        )
        return

    dsn = dsn if dsn is not None else os.environ.get("DATABASE_URL", "")
    if not dsn:
        # No DSN set means the harness will fall back to its own temp SQLite file.
        return

    scheme = dsn.partition("://")[0].split("+", 1)[0].lower()
    if scheme.startswith("sqlite"):
        return

    host = _host_of(dsn)
    if host in _LOCAL_HOSTS:
        return

    raise UnsafeTestDatabaseError(
        "Refusing to run tests against a non-local database.\n"
        f"  DATABASE_URL host: {host}\n"
        "This suite calls create_all and seeds a default tenant and user id=1 before "
        "every test, then runs each test's own writes. Against a real deployment that "
        "is data loss.\n"
        "Unset DATABASE_URL to use the harness's temporary SQLite database, or point it "
        "at localhost. If you genuinely mean to write to a remote throwaway database, "
        f"set {_OVERRIDE_ENV}=1."
    )
