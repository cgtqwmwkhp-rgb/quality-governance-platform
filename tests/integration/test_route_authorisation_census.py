"""Census every endpoint the app serves, and refuse an undeclared one.

What this replaces
------------------
The authorisation gap was previously measured by sampling: 45 endpoints were read
by hand and 6 were found to check a permission. The routers are far too uneven for
that to mean anything — some gate every write, others gate none — so this file
counts all of them instead. The real figures are printed by
``test_census_is_reported_for_the_record``.

Why this is the enforcement, not just a report
----------------------------------------------
``test_every_endpoint_is_either_checked_or_declared`` fails when a route is
neither authorisation-checked nor named in
``src/domain/authz/route_declarations.py``. A new route therefore cannot merge
without somebody deciding which it is, and the ceilings in that module close the
easy escape of declaring it as debt. That is the fail-closed property: an endpoint
whose authorisation nobody has determined does not ship.

Why this lives in the integration suite
---------------------------------------
Importing ``src.main`` opens a database engine at import time. This suite's
conftest calls ``assert_test_database_is_local`` before that happens, so the app
can be imported here with no risk of pointing an engine at a live deployment. The
classification logic itself needs none of this and is pinned without an app in
``tests/unit/test_route_census_classification.py``; the FastAPI-shape handling it
relies on is pinned in ``tests/unit/test_permission_route_walk.py``.

A green run here does not prove authorisation *works*
-----------------------------------------------------
It proves every endpoint's posture is accounted for. 474 of them are accounted for
as having no authorisation check at all. The UX coverage gate has the same
limitation for a different reason: its ``PORTAL_TEST_TOKEN`` is an admin token, so
a permission failure would not necessarily surface there either.
"""

from __future__ import annotations

import pytest

from src.domain.authz.census import Posture, format_undeclared_report, take_census
from src.domain.authz.route_declarations import (
    AUTHENTICATED_ONLY_DEBT,
    DECLARED_ENDPOINTS,
    MAX_AUTHENTICATED_ONLY_DEBT,
    MAX_PUBLIC_BY_DESIGN,
    MAX_SUPERUSER_ONLY,
    PUBLIC_BY_DESIGN,
)

#: A floor, not an expected value: far below the real count so ordinary growth
#: never trips it, while an app that is not really mounted does. Matches the
#: floor in test_permission_routes_catalogue.py, which found 6 routes instead of
#: 980 the first time FastAPI changed how include_router works.
MIN_ENDPOINTS = 500

#: The shortest a public-endpoint justification may be. Short enough to allow a
#: genuinely one-line reason, long enough that "ok" or "public" fails.
MIN_REASON_LENGTH = 40


@pytest.fixture(scope="module")
def census():
    # Imported here rather than at module scope: src/domain may not depend on
    # src/api (scripts/check_import_boundaries.py enforces it), so wiring the app
    # into the census is the caller's job.
    from src.core.config import settings
    from src.main import app

    # The mounted surface is environment-dependent, so the declarations can only
    # match one environment. src/api/__init__.py mounts the /testing router only
    # when not is_production, and src/main.py passes docs_url/redoc_url/
    # openapi_url as None when it is. Measuring under production settings would
    # therefore find ten fewer endpoints and report the declarations as stale, for
    # a reason that has nothing to do with authorisation. The counts recorded in
    # route_declarations.py are the full development/staging surface, which is the
    # larger one and so the safe one to hold to a ceiling.
    assert not settings.is_production, (
        "the census is recorded against the non-production route surface, which includes the "
        "/testing router and the FastAPI docs routes. Running it under production settings "
        "measures a smaller app and would report the declarations as stale."
    )

    return take_census(app)


# --------------------------------------------------------------------------- #
# Guards against this file passing without checking anything
# --------------------------------------------------------------------------- #


def test_the_app_is_actually_mounted(census) -> None:
    """Without this, every assertion below passes by classifying nothing."""
    assert len(census.endpoints) >= MIN_ENDPOINTS, (
        f"only {len(census.endpoints)} endpoints were classified. The app is not fully mounted, "
        "so this file's guarantees would be vacuous rather than satisfied."
    )
    assert census.counts[Posture.PERMISSION] > 0, "no endpoint appears to check a permission at all"
    assert DECLARED_ENDPOINTS, "route_declarations.py declares nothing"


def test_every_posture_is_represented_in_the_totals(census) -> None:
    """The postures must partition the endpoints, or some are uncounted."""
    assert sum(census.counts.values()) == len(census.endpoints)


# --------------------------------------------------------------------------- #
# The enforcement
# --------------------------------------------------------------------------- #


def test_every_endpoint_is_either_checked_or_declared(census) -> None:
    """The fail-closed gate. A new route must be gated, or explicitly accounted for.

    If this fails for a route you have just added, the fix is one of:

    * add ``Depends(require_permission("<token>"))`` and put the token in
      ``src/domain/authz/catalogue.py`` — the ordinary answer for anything that
      reads or writes tenant data;
    * add it to ``PUBLIC_BY_DESIGN`` with a reason, if it genuinely must serve an
      unauthenticated caller. That list has a ceiling, so this is conspicuous.

    Adding it to ``AUTHENTICATED_ONLY_DEBT`` is deliberately not an option: that
    list is at its ceiling, so it cannot absorb anything new.
    """
    undeclared = census.undeclarable_keys - DECLARED_ENDPOINTS
    assert not undeclared, format_undeclared_report(census, declared=DECLARED_ENDPOINTS)


def test_no_declaration_is_stale(census) -> None:
    """A declaration for a route that is gone, or now gated, is an exemption nobody checks."""
    stale = DECLARED_ENDPOINTS - census.undeclarable_keys
    detail = "\n".join(f"  {method} {path}" for method, path in sorted(stale))
    assert not stale, (
        f"{len(stale)} declaration(s) in src/domain/authz/route_declarations.py no longer "
        f"describe an endpoint that needs one:\n{detail}\n"
        "Either the route was deleted, or it now performs an authorisation check. Remove the "
        "entry — and if it was debt, that is the count going down."
    )


def test_the_authenticated_only_gap_has_not_grown(census) -> None:
    """The ceiling. Closing a route's gap lowers this; a new gap cannot raise it."""
    measured = census.counts[Posture.AUTHENTICATED_ONLY]
    assert measured <= MAX_AUTHENTICATED_ONLY_DEBT, (
        f"{measured} endpoints authenticate without authorising, above the recorded ceiling of "
        f"{MAX_AUTHENTICATED_ONLY_DEBT}. A new route must check a permission rather than join "
        "this list. If the increase is genuinely intended, MAX_AUTHENTICATED_ONLY_DEBT in "
        "src/domain/authz/route_declarations.py has to be raised deliberately."
    )
    assert len(AUTHENTICATED_ONLY_DEBT) == measured, (
        f"the debt list holds {len(AUTHENTICATED_ONLY_DEBT)} entries but the census finds "
        f"{measured}. They must agree exactly, or the list is either hiding a gap or claiming "
        "one that has been fixed."
    )


def test_the_public_surface_has_not_grown(census) -> None:
    measured = census.counts[Posture.UNAUTHENTICATED] + census.counts[Posture.OPTIONAL_AUTH]
    assert measured <= MAX_PUBLIC_BY_DESIGN, (
        f"{measured} endpoints establish no caller identity, above the recorded ceiling of "
        f"{MAX_PUBLIC_BY_DESIGN}. Adding an unauthenticated endpoint is a decision that needs "
        "making on purpose."
    )
    assert (
        len(PUBLIC_BY_DESIGN) == measured
    ), f"PUBLIC_BY_DESIGN holds {len(PUBLIC_BY_DESIGN)} entries but the census finds {measured}."


def test_the_gap_is_not_closed_by_making_things_superuser_only(census) -> None:
    """Superuser-only counts as authorisation, so it could be used to fake progress.

    ``User.has_permission`` returns ``True`` for a superuser before it reads any
    role, so an endpoint moved behind a superuser gate cannot be opened up again by
    granting a permission — only by editing the route. Converting the gap to
    superuser-only would therefore report as fixed while leaving the product
    usable by one account.
    """
    measured = census.counts[Posture.SUPERUSER]
    assert measured <= MAX_SUPERUSER_ONLY, (
        f"{measured} endpoints are gated on superuser alone, above the recorded ceiling of "
        f"{MAX_SUPERUSER_ONLY}. Prefer a named permission: a superuser gate cannot be delegated "
        "to a role."
    )


# --------------------------------------------------------------------------- #
# The declarations themselves
# --------------------------------------------------------------------------- #


def test_public_and_debt_declarations_do_not_overlap() -> None:
    overlap = sorted(set(PUBLIC_BY_DESIGN) & AUTHENTICATED_ONLY_DEBT)
    assert not overlap, f"{overlap} are declared both public by design and authenticated-only debt"


def test_every_public_endpoint_has_a_real_reason() -> None:
    """An unjustified public endpoint is indistinguishable from a forgotten one."""
    vague = sorted(key for key, reason in PUBLIC_BY_DESIGN.items() if len(reason.strip()) < MIN_REASON_LENGTH)
    assert not vague, (
        f"{vague} are declared public with no real explanation. Say what makes the endpoint safe "
        "to serve without a session — a different credential, a statutory duty, or the absence of "
        "any tenant data."
    )


def test_declared_endpoints_match_the_two_lists_exactly() -> None:
    """``DECLARED_ENDPOINTS`` is what the gate reads; it must not drift from its sources."""
    assert DECLARED_ENDPOINTS == frozenset(PUBLIC_BY_DESIGN) | AUTHENTICATED_ONLY_DEBT


# --------------------------------------------------------------------------- #
# The measurement, for the record
# --------------------------------------------------------------------------- #


def test_census_is_reported_for_the_record(census, capsys) -> None:
    """Print the census. This is the C-2 number, replacing the 45-endpoint sample."""
    summary = census.format_summary()
    assert "endpoints" in summary

    writes = [
        endpoint
        for endpoint in census.with_posture(Posture.AUTHENTICATED_ONLY)
        if endpoint.method in ("POST", "PUT", "PATCH", "DELETE")
    ]

    with capsys.disabled():
        print("\nRoute authorisation census\n" + summary)
        print(f"of the authenticated-only endpoints, {len(writes)} are writes:")
        for endpoint in sorted(writes, key=lambda e: (e.path, e.method)):
            print(f"    {endpoint}")
