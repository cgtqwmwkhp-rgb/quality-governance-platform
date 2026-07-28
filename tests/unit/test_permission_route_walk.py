"""Pin the route walk against the FastAPI version actually installed.

``tokens_from_registered_routes`` is one half of the code/catalogue cross-check,
and it is the half that depends on FastAPI's internal shape. That shape changed
underneath it: up to FastAPI 0.135 ``include_router`` copied every route onto
``app.routes``, so a flat loop over that list saw all of them. From 0.140 it
appends a single wrapper holding the original router instead, and the routes
below it are reachable only by descending into it. The same flat loop that found
980 routes locally found 6 in CI, and the cross-check went from meaningful to
vacuous purely because of a dependency upgrade.

These tests build a small app whose shape mirrors the real one — a router
included into a router included into the app — and assert the walk finds what is
underneath. They need no database, no mounted application and no network, so
they run in the unit suite and fail in about a second. That matters: the
alternative is discovering the same breakage from the integration suite's
vacuity floor, which tells you the count is wrong but not why.

If a future FastAPI rearranges routing again, this file is what fails, and it
fails saying which nesting level stopped being visible.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI

from src.api.dependencies import require_permission
from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR, RouteWalkError, tokens_from_registered_routes


def _tagged_checker(token: str):
    """A stand-in for a ``require_permission`` checker, tagged the same way."""

    async def permission_checker() -> None:
        return None

    setattr(permission_checker, REQUIRED_PERMISSION_ATTR, token)
    return permission_checker


@pytest.fixture
def nested_app() -> FastAPI:
    """An app shaped like the real one: leaf router -> mid router -> app."""
    leaf = APIRouter()

    @leaf.get("/{item_id}", dependencies=[Depends(_tagged_checker("incident:read"))])
    def read(item_id: int) -> dict:
        return {}

    @leaf.delete("/{item_id}", dependencies=[Depends(_tagged_checker("incident:delete"))])
    def delete(item_id: int) -> dict:
        return {}

    mid = APIRouter()
    mid.include_router(leaf, prefix="/incidents")

    # A permission attached to a whole router rather than one route. Nothing in
    # the repo does this today, which is exactly why it is tested: it is the
    # wiring a source scan cannot see, so if the walk stops seeing it too then
    # nothing sees it.
    gated = APIRouter(dependencies=[Depends(_tagged_checker("admin:manage"))])

    @gated.get("/secrets")
    def secrets() -> dict:
        return {}

    mid.include_router(gated, prefix="/admin")

    app = FastAPI()
    app.include_router(mid, prefix="/api/v1")

    @app.get("/healthz")
    def healthz() -> dict:
        return {}

    return app


def test_tokens_are_found_through_two_levels_of_include_router(nested_app: FastAPI) -> None:
    result = tokens_from_registered_routes(nested_app)

    assert result.token_set == {"incident:read", "incident:delete", "admin:manage"}, (
        "the walk lost tokens nested under include_router. FastAPI's routing shape has "
        "probably changed again; see _visit_route_node in src/domain/authz/extraction.py."
    )


def test_routes_below_an_included_router_are_counted(nested_app: FastAPI) -> None:
    """The count is what the integration vacuity floor relies on."""
    result = tokens_from_registered_routes(nested_app)

    assert result.route_count == 4, (
        f"expected 4 endpoints (3 nested + /healthz), counted {result.route_count}. A count that "
        "only sees routes declared directly on the app is the failure this file exists to catch."
    )


def test_labels_carry_the_prefix_the_route_is_served_under(nested_app: FastAPI) -> None:
    """Labels are diagnostics, but a wrong prefix means the walk lost its place."""
    result = tokens_from_registered_routes(nested_app)

    assert any("/api/v1/incidents/{item_id}" in label for label in result.tokens["incident:read"]), (
        f"labels for incident:read were {sorted(result.tokens['incident:read'])}; the /api/v1 and "
        "/incidents prefixes were not accumulated while descending."
    )


def test_an_untagged_permission_checker_is_reported_not_ignored() -> None:
    """A second checker factory that forgot the tag must be loud, not invisible."""

    async def permission_checker() -> None:
        return None

    # The name is how an untagged checker is recognised; mimic what
    # require_permission's inner function is called.
    permission_checker.__qualname__ = "require_permission.<locals>.permission_checker"

    router = APIRouter()

    @router.get("/x", dependencies=[Depends(permission_checker)])
    def x() -> dict:
        return {}

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    result = tokens_from_registered_routes(app)

    assert not result.token_set
    assert result.untagged_checkers, (
        "an untagged permission checker on a nested route was neither read nor reported, so "
        "enforcement would silently vanish from the cross-check."
    )


def test_the_real_require_permission_is_readable_by_the_walk() -> None:
    """The production factory, not a stand-in — the tag must survive FastAPI's wiring."""
    router = APIRouter()

    @router.get("/thing", dependencies=[Depends(require_permission("incident:read"))])
    def thing() -> dict:
        return {}

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    result = tokens_from_registered_routes(app)

    assert result.token_set == {"incident:read"}
    assert not result.untagged_checkers


def test_an_endpoint_is_not_mistaken_for_a_checker_by_its_name() -> None:
    """The untagged-checker heuristic matches a qualname component, not a substring.

    A handler defined inside a function whose own name contains
    ``require_permission`` — such as a test — inherits that text in its qualname
    and used to be reported as an untagged checker. A false report here is not
    harmless: it fails the cross-check for a reason that has nothing to do with
    permissions, and the quickest way to make that go away is to weaken the
    check.
    """

    def helper_that_mentions_require_permission_in_its_name() -> FastAPI:
        router = APIRouter()

        @router.get("/thing", dependencies=[Depends(_tagged_checker("incident:read"))])
        def thing() -> dict:
            return {}

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    result = tokens_from_registered_routes(helper_that_mentions_require_permission_in_its_name())

    assert result.token_set == {"incident:read"}
    assert not result.untagged_checkers


def test_a_cyclic_router_graph_raises_rather_than_hanging() -> None:
    """Termination is enforced, not assumed."""

    class SelfReferencingRouter:
        path = "/loop"

        @property
        def routes(self):
            return [SelfReferencingRouter()]

    with pytest.raises(RouteWalkError):
        tokens_from_registered_routes(SelfReferencingRouter())
