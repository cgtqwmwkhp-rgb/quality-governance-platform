"""Pin how the census classifies a route, without a mounted app or a database.

The census is only useful if a wrong answer is a loud one. Two failure directions
matter, and they are not symmetric:

*Over-reporting protection* is the dangerous one. If a route with no
authorisation were classified as authorisation-checked, it would need no
declaration, and the enforcement gap would shrink on paper without anything
changing. Every test here that asserts a *weak* posture is guarding that.

*Under-reporting* is safe but noisy: a gated route misread as a gap would demand a
declaration it should not need, and the ceiling in
``src/domain/authz/route_declarations.py`` would refuse it. Loud, and in the right
direction.

The real app is classified in ``tests/integration/test_route_authorisation_census.py``,
because importing ``src.main`` opens a database engine and only that suite's
conftest asserts the DSN is local first. The FastAPI-shape handling the census
depends on is pinned separately in ``tests/unit/test_permission_route_walk.py``.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI

from src.api.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_current_user,
    get_optional_current_user,
    require_permission,
)
from src.domain.authz.census import (
    AUTHENTICATION_KIND_ATTR,
    DuplicateEndpointKeyError,
    Posture,
    format_undeclared_report,
    take_census,
)
from src.domain.authz.extraction import RouteWalkError


def _bare_app() -> FastAPI:
    """A FastAPI app with no documentation routes.

    ``FastAPI()`` installs ``/docs``, ``/docs/oauth2-redirect``, ``/redoc`` and
    ``/openapi.json``, each served for GET and HEAD, so a default app carries eight
    endpoints before a single route is declared. The census counts them — that is
    the point of ``test_a_starlette_route_with_no_dependency_graph_is_counted_not_skipped``
    — but they are noise in a test about one route's posture, so they are switched
    off here rather than filtered out afterwards.
    """
    return FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _app(build) -> FastAPI:
    """Mount ``build``'s router the way the real app does: nested, under a prefix."""
    router = APIRouter()
    build(router)
    outer = APIRouter()
    outer.include_router(router, prefix="/things")
    app = _bare_app()
    app.include_router(outer, prefix="/api/v1")
    return app


def _posture_of(app: FastAPI, method: str, path: str) -> Posture:
    census = take_census(app)
    matching = [endpoint for endpoint in census.endpoints if endpoint.key == (method, path)]
    assert matching, f"{method} {path} not found; census has {[str(e) for e in census.endpoints]}"
    return matching[0].posture


# --------------------------------------------------------------------------- #
# The postures, one at a time
# --------------------------------------------------------------------------- #


def test_a_require_permission_route_reports_its_token() -> None:
    def build(router: APIRouter) -> None:
        @router.post("/", dependencies=[Depends(require_permission("incident:create"))])
        def create() -> dict:
            return {}

    census = take_census(_app(build))
    (endpoint,) = census.endpoints
    assert endpoint.posture is Posture.PERMISSION
    assert endpoint.permissions == ("incident:create",)
    assert endpoint.posture.is_authorisation_checked
    assert not endpoint.posture.must_be_declared


def test_a_superuser_route_is_authorisation_checked_but_holds_no_permission() -> None:
    def build(router: APIRouter) -> None:
        @router.delete("/{thing_id}")
        def delete(thing_id: int, user=Depends(get_current_superuser)) -> dict:
            return {}

    census = take_census(_app(build))
    (endpoint,) = census.endpoints
    assert endpoint.posture is Posture.SUPERUSER
    assert endpoint.permissions == ()
    assert endpoint.posture.is_authorisation_checked


@pytest.mark.parametrize("dependency", [get_current_user, get_current_active_user])
def test_an_authenticated_route_with_no_permission_is_the_gap(dependency) -> None:
    """The posture C-2 counts. Misreporting this one hides the defect."""

    def build(router: APIRouter) -> None:
        @router.get("/")
        def read(user=Depends(dependency)) -> dict:
            return {}

    census = take_census(_app(build))
    (endpoint,) = census.endpoints
    assert endpoint.posture is Posture.AUTHENTICATED_ONLY
    assert not endpoint.posture.is_authorisation_checked
    assert endpoint.posture.must_be_declared


def test_optional_authentication_is_not_counted_as_authenticated() -> None:
    """``get_optional_current_user`` serves an anonymous caller, so it gates nothing."""

    def build(router: APIRouter) -> None:
        @router.post("/")
        def submit(user=Depends(get_optional_current_user)) -> dict:
            return {}

    assert _posture_of(_app(build), "POST", "/api/v1/things/") is Posture.OPTIONAL_AUTH


def test_a_route_with_no_dependencies_is_unauthenticated() -> None:
    def build(router: APIRouter) -> None:
        @router.get("/open")
        def open_endpoint() -> dict:
            return {}

    assert _posture_of(_app(build), "GET", "/api/v1/things/open") is Posture.UNAUTHENTICATED


def test_a_websocket_route_is_censused_under_the_websocket_method() -> None:
    """A websocket declares no HTTP method, and must not vanish from the count."""

    def build(router: APIRouter) -> None:
        @router.websocket("/ws/{room}")
        async def socket(websocket, room: str) -> None:  # pragma: no cover - never called
            return None

    census = take_census(_app(build))
    (endpoint,) = census.endpoints
    assert endpoint.key == ("WEBSOCKET", "/api/v1/things/ws/{room}")
    assert endpoint.posture is Posture.UNAUTHENTICATED


# --------------------------------------------------------------------------- #
# Fail-closed behaviour of the classifier itself
# --------------------------------------------------------------------------- #


def test_an_unstamped_authentication_dependency_reads_as_unauthenticated() -> None:
    """A new auth dependency that forgets the tag must not pass for authenticating.

    This is the classifier's own fail-closed property. The posture is derived from
    :data:`AUTHENTICATION_KIND_ATTR`, never from the callable's name, so a
    dependency that looks like authentication but is not tagged lands in the
    posture that has to be declared route by route — and the declaration ceiling
    refuses to absorb it quietly.
    """

    async def get_current_user_lookalike() -> None:
        return None

    def build(router: APIRouter) -> None:
        @router.get("/")
        def read(user=Depends(get_current_user_lookalike)) -> dict:
            return {}

    assert not hasattr(get_current_user_lookalike, AUTHENTICATION_KIND_ATTR)
    assert _posture_of(_app(build), "GET", "/api/v1/things/") is Posture.UNAUTHENTICATED


def test_an_unrecognised_authentication_tag_reads_as_unauthenticated() -> None:
    """A tag value the census does not understand must not be treated as a gate."""

    async def oddly_tagged() -> None:
        return None

    setattr(oddly_tagged, AUTHENTICATION_KIND_ATTR, "something-new")

    def build(router: APIRouter) -> None:
        @router.get("/")
        def read(user=Depends(oddly_tagged)) -> dict:
            return {}

    assert _posture_of(_app(build), "GET", "/api/v1/things/") is Posture.UNAUTHENTICATED


def test_a_router_level_permission_gates_the_routes_beneath_it() -> None:
    """Permissions attached to a router must reach the endpoints they protect.

    Read from the include context as well as the route's own dependency graph,
    because the FastAPI versions that do not flatten ``include_router`` leave them
    only on the context. Missing them would report a gated route as a gap.
    """
    gated = APIRouter(dependencies=[Depends(require_permission("admin:manage"))])

    @gated.get("/secrets")
    def secrets() -> dict:
        return {}

    app = _bare_app()
    app.include_router(gated, prefix="/api/v1/admin")

    census = take_census(app)
    (endpoint,) = census.endpoints
    assert endpoint.posture is Posture.PERMISSION
    assert endpoint.permissions == ("admin:manage",)


def test_a_permission_dependency_wins_over_an_authentication_dependency() -> None:
    """Both are usually present; the stronger posture is the true one."""

    def build(router: APIRouter) -> None:
        @router.post("/", dependencies=[Depends(require_permission("incident:create"))])
        def create(user=Depends(get_current_user)) -> dict:
            return {}

    assert _posture_of(_app(build), "POST", "/api/v1/things/") is Posture.PERMISSION


def test_a_starlette_route_with_no_dependency_graph_is_counted_not_skipped() -> None:
    """A route added with ``add_route`` must not be invisible to the census.

    This was a hole in the walk. FastAPI installs ``/docs``, ``/redoc`` and
    ``/openapi.json`` this way, and the walk reached those nodes and skipped them
    because they carry no resolved dependency graph. Anything added the same way
    served traffic while no part of this machinery could see it, so nobody would
    ever have been asked whether it needed authorisation.
    """

    def endpoint(request):  # pragma: no cover - never called
        return None

    app = _bare_app()
    app.add_route("/raw", endpoint, methods=["GET"])

    census = take_census(app)
    raw = [item for item in census.endpoints if item.path == "/raw"]

    assert raw, f"the walk skipped /raw; it saw {[str(e) for e in census.endpoints]}"
    # Starlette serves HEAD alongside GET, and both are counted: a declaration is
    # keyed on the method, so a HEAD that nothing had accounted for would be a hole.
    assert {item.method for item in raw} == {"GET", "HEAD"}
    for item in raw:
        assert item.posture is Posture.UNAUTHENTICATED
        assert item.posture.must_be_declared
        assert not item.dependencies_readable, (
            "an endpoint with no readable dependency graph must say so. Reporting it as ungated "
            "without that distinction confuses 'nothing gates it' with 'nothing could be read'."
        )
    assert census.with_unreadable_dependencies == tuple(raw)


def test_an_unclassifiable_route_like_node_raises() -> None:
    """Anything with a path that the walk cannot read must be loud, not skipped.

    The rule the whole authz package is built on: a walk that silently stops
    seeing things is worse than no walk. A node carrying a path but no endpoint,
    no dependency graph and no routes is a shape this code does not understand,
    and guessing that it is harmless is how the previous hole appeared.
    """

    class UnknownRouteShape:
        path = "/mystery"

    class AppLikeHolder:
        routes = [UnknownRouteShape()]

    with pytest.raises(RouteWalkError) as excinfo:
        take_census(AppLikeHolder())

    assert "/mystery" in str(excinfo.value)


def test_two_endpoints_sharing_a_method_and_path_are_refused() -> None:
    """A declaration is keyed on (method, path), so a duplicate key would blur two routes.

    Refused rather than de-duplicated: whichever route loses would be covered by a
    justification written for the other, and nobody would know.
    """
    app = _bare_app()

    first = APIRouter()

    @first.get("/clash")
    def one() -> dict:
        return {}

    second = APIRouter()

    @second.get("/clash")
    def two() -> dict:
        return {}

    app.include_router(first, prefix="/api/v1")
    app.include_router(second, prefix="/api/v1")

    with pytest.raises(DuplicateEndpointKeyError) as excinfo:
        take_census(app)

    assert "/api/v1/clash" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def test_the_undeclared_report_names_the_route_and_its_handler() -> None:
    """The failure message has to be actionable without re-running anything."""

    def build(router: APIRouter) -> None:
        @router.get("/forgotten")
        def forgotten(user=Depends(get_current_user)) -> dict:
            return {}

    census = take_census(_app(build))
    report = format_undeclared_report(census, declared=set())

    assert "1 endpoint(s) have no authorisation declaration" in report
    assert "/api/v1/things/forgotten" in report
    assert "authenticated_only" in report
    assert "forgotten" in report


def test_a_declared_route_is_absent_from_the_report() -> None:
    def build(router: APIRouter) -> None:
        @router.get("/known")
        def known(user=Depends(get_current_user)) -> dict:
            return {}

    census = take_census(_app(build))
    report = format_undeclared_report(census, declared={("GET", "/api/v1/things/known")})

    assert "0 endpoint(s) have no authorisation declaration" in report


def test_the_summary_counts_add_up_to_the_endpoint_total() -> None:
    """A posture missing from the summary would hide endpoints from the census."""

    def build(router: APIRouter) -> None:
        @router.post("/", dependencies=[Depends(require_permission("incident:create"))])
        def create() -> dict:
            return {}

        @router.get("/")
        def read(user=Depends(get_current_user)) -> dict:
            return {}

        @router.get("/open")
        def open_endpoint() -> dict:
            return {}

    census = take_census(_app(build))
    assert sum(census.counts.values()) == len(census.endpoints) == 3
    assert "endpoints                        : 3" in census.format_summary()
