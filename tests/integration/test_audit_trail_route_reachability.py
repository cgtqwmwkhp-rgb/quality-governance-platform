"""Audit-trail literal routes must be reachable, not shadowed by ``/{entry_id}``.

FastAPI matches routes in declaration order, so a ``@router.get("/{entry_id}")``
declared before ``@router.get("/stats")`` answers ``GET /audit-trail/stats`` and
rejects it with a 422 ``path -> entry_id`` int-parsing error. Every one of these
paths still appears in the OpenAPI document while that is true, so neither the
schema snapshot nor the contract tests notice — the only thing that catches it is
driving the real router.

``/audit-trail/verifications`` is the only read surface for the tamper-evident
hash chain, and ``/stats`` and ``/entity-types`` are how audit coverage per module
is reported for ISO 9001/45001, so these being silently dead is an evidence gap.

Scope: this module pins the ``audit_trail.py`` router specifically. The
repository-wide equivalent is ``tests/integration/test_route_shadowing_guard.py``
(PR #1397), which sweeps every router for the same defect class; while that PR is
in flight its audit-trail coverage is deliberately xfailed pending this fix. The
two are kept separate on purpose — the sweep proves no route anywhere is dead,
this module proves the specific ordering constraint documented in
``audit_trail.py`` holds, and it keeps holding if the repo-wide guard is ever
narrowed. This module additionally drives real HTTP, which the sweep only does
for the routes its own branch fixes.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

import pytest
from starlette.routing import Match

from src.main import app

PREFIX = "/api/v1/audit-trail"

# The literal paths that sit alongside the ``/{entry_id}`` catch-all.
LITERAL_PATHS = [
    f"{PREFIX}/actions",
    f"{PREFIX}/entity-types",
    f"{PREFIX}/stats",
    f"{PREFIX}/verifications",
]

CATCH_ALL_PATH = f"{PREFIX}/{{entry_id}}"


# ---------------------------------------------------------------------------
# Flattening the router tree into matcher scan order
# ---------------------------------------------------------------------------


def _iter_scan_order(routes: Iterable[Any], _depth: int = 0) -> Iterator[Any]:
    """Flatten the router tree into the order the matcher actually scans it.

    Two representations exist in the versions this repository runs against:

    * **Flat** (FastAPI 0.135.x, installed on some machines here) — ``include_router``
      copies every leaf into ``app.routes``, which is a single flat list.
    * **Nested** (FastAPI 0.140.7, which ``requirements.lock`` pins and CI resolves
      to) — included routers stay nested under a private ``_IncludedRouter`` whose
      own ``path`` is ``None``. Its ``effective_route_contexts()`` yields the leaves,
      already fully expanded, in declaration order.

    This dispatches on the presence of ``effective_route_contexts`` rather than
    isinstance-checking ``_IncludedRouter``. The class is private, underscore-prefixed
    and does not exist at all on the older version, so keying on it would both break
    on a rename and need a separate code path per shape; the accessor is the public
    surface and its absence is exactly what identifies an already-flat route. The
    recursion is defensive — 0.140.7 returns leaves with no further nesting, but a
    version that returns nested contexts would otherwise be silently half-walked.
    """
    if _depth > 10:
        raise RuntimeError("Router tree deeper than 10 levels; refusing to recurse further")
    for route in routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from _iter_scan_order(contexts(), _depth + 1)
        else:
            yield route


SCAN_ORDER: list[Any] = list(_iter_scan_order(app.routes))
HTTP_ROUTES: list[Any] = [r for r in SCAN_ORDER if getattr(r, "methods", None) and getattr(r, "path", None)]
AUDIT_ROUTES: list[Any] = [r for r in HTTP_ROUTES if r.path.startswith(PREFIX)]


def _resolve(method: str, path: str) -> Any:
    """Return the route Starlette would dispatch to, mirroring ``Router.app``.

    First FULL match wins; a PARTIAL (path matched, method did not) is held aside
    and only used if nothing fully matches.
    """
    scope = {"type": "http", "method": method, "path": path, "headers": [], "root_path": ""}
    partial = None
    for route in SCAN_ORDER:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
        if match == Match.PARTIAL and partial is None:
            partial = route
    return partial


def _is_entry_id_parse_error(response) -> bool:
    """True if the response is the 422 produced by feeding a literal to ``entry_id``."""
    if response.status_code != 422:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    errors = body.get("error", {}).get("details", {}).get("errors", [])
    if not isinstance(errors, list):
        return False
    return any("entry_id" in str(err.get("field", "")) and err.get("type") == "int_parsing" for err in errors)


# ---------------------------------------------------------------------------
# Self-check
#
# Everything below introspects the flattened router table, so if the flattening
# returns nothing the assertions pass while checking nothing. That is not
# hypothetical: the first version of this module walked ``app.routes`` directly,
# which is flat on FastAPI 0.135.2 and nested on the 0.140.7 that CI installs, and
# it went red in CI having been green locally. Prove the table was actually seen
# before trusting any result derived from it.
# ---------------------------------------------------------------------------


class TestRouterTableWasActuallyInspected:
    def test_the_whole_router_table_is_flattened(self) -> None:
        assert len(HTTP_ROUTES) > 500, (
            f"Only {len(HTTP_ROUTES)} HTTP routes were flattened out of the app, which is far "
            f"below the ~970 this application registers. The router tree representation has "
            f"changed and _iter_scan_order no longer walks it, so every introspection assertion "
            f"in this module is passing vacuously."
        )

    def test_the_audit_trail_router_is_present_in_full(self) -> None:
        """The ten routes declared in ``audit_trail.py`` must all be visible."""
        assert len(AUDIT_ROUTES) >= 10, (
            f"Only {len(AUDIT_ROUTES)} {PREFIX} routes were found, but audit_trail.py declares "
            f"ten. The flattening is dropping routes: {sorted(r.path for r in AUDIT_ROUTES)}"
        )

    @pytest.mark.parametrize("path", LITERAL_PATHS + [CATCH_ALL_PATH])
    def test_each_path_under_test_is_present(self, path: str) -> None:
        """Anchor on the exact paths asserted below, so a silent drop cannot hide."""
        assert any(
            r.path == path and "GET" in r.methods for r in AUDIT_ROUTES
        ), f"GET {path} is not in the flattened router table"

    def test_the_matcher_resolves_an_unambiguous_route_to_itself(self) -> None:
        """Sanity-check ``_resolve`` against a route nothing can shadow."""
        winner = _resolve("GET", "/health")
        assert winner is not None and winner.path == "/health"


# ---------------------------------------------------------------------------
# The four previously-dead literals
# ---------------------------------------------------------------------------


class TestLiteralRoutesAreReachable:
    @pytest.mark.parametrize("path", LITERAL_PATHS)
    def test_literal_path_resolves_to_its_own_handler(self, path: str) -> None:
        """The literal route answers, not the ``/{entry_id}`` catch-all.

        Names the winning route, so a failure says what is shadowing what rather
        than only that something is wrong.
        """
        route = _resolve("GET", path)
        assert route is not None, f"GET {path} matched no route at all"
        assert route.path == path, (
            f"GET {path} is dispatched to {route.path} ({getattr(route, 'name', '?')}). "
            f"A path-parameter route declared earlier is shadowing it."
        )

    @pytest.mark.parametrize("path", LITERAL_PATHS)
    async def test_literal_path_is_not_swallowed_by_entry_id(self, admin_client, path: str) -> None:
        """Drive the real router — this is the assertion that does not depend on
        how the framework happens to represent its route table."""
        response = await admin_client.get(path)
        assert not _is_entry_id_parse_error(response), (
            f"GET {path} returned the entry_id int-parsing 422, so it is being matched "
            f"as /{{entry_id}} and is unreachable. Body: {response.text}"
        )
        # Guard against the endpoint being unreachable for some other reason.
        assert response.status_code != 404, f"GET {path} returned 404: {response.text}"

    async def test_actions_returns_the_action_reference(self, admin_client) -> None:
        """Not merely 'not a 422' — the body proves which handler answered.

        ``list_actions`` returns a fixed dict of action groups; ``get_audit_entry``
        could not produce this shape, so a correct body rules out the request having
        been answered by some other route that also happens to return 200.
        """
        response = await admin_client.get(f"{PREFIX}/actions")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, dict)
        assert {"data", "auth", "admin", "system"} <= set(body), body

    async def test_entity_types_returns_the_auditable_entity_list(self, admin_client) -> None:
        """Same reasoning as above: the payload is a literal list in ``audit_trail.py``."""
        response = await admin_client.get(f"{PREFIX}/entity-types")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list)
        assert "incident" in body and "audit" in body, body

    @pytest.mark.parametrize(
        "path,expected_type",
        [(f"{PREFIX}/stats", dict), (f"{PREFIX}/verifications", list)],
    )
    async def test_db_backed_literals_return_their_own_container_shape(
        self, admin_client, path: str, expected_type: type
    ) -> None:
        """Shape only, deliberately.

        ``/stats`` and ``/verifications`` are served through ``AuditLogService``,
        which another lane is editing. Asserting on their field names would couple
        this routing test to that lane's work; the container type is enough to show
        the intended handler answered, because the by-id route returns a single
        entry object and never a bare list.
        """
        response = await admin_client.get(path)
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), expected_type)


# ---------------------------------------------------------------------------
# The by-id route must survive the move
# ---------------------------------------------------------------------------


class TestEntryIdLookupStillWorks:
    async def test_missing_entry_is_a_not_found_over_http(self, admin_client) -> None:
        response = await admin_client.get(f"{PREFIX}/999999")
        assert not _is_entry_id_parse_error(response), response.text
        assert response.status_code == 404, f"expected a not-found for a missing entry, got {response.text}"

    def test_numeric_path_still_resolves_to_the_catch_all(self) -> None:
        route = _resolve("GET", f"{PREFIX}/999999")
        assert route is not None and route.path == CATCH_ALL_PATH, (
            f"GET {PREFIX}/999999 now resolves to {getattr(route, 'path', None)}, "
            f"not {CATCH_ALL_PATH}. The move broke the by-id lookup."
        )


# ---------------------------------------------------------------------------
# The ordering constraint itself
# ---------------------------------------------------------------------------


def test_no_audit_trail_literal_is_declared_after_the_catch_all() -> None:
    """Catch future literals added below ``/{entry_id}``, not just today's four.

    Registration order is what actually decides this, so assert on it directly
    rather than re-listing the paths we happen to know about. This is the
    executable form of the section comment in ``audit_trail.py``.
    """
    catch_all_index = next(
        (i for i, r in enumerate(AUDIT_ROUTES) if r.path == CATCH_ALL_PATH and "GET" in r.methods),
        None,
    )
    assert catch_all_index is not None, (
        f"{CATCH_ALL_PATH} was not found among the {len(AUDIT_ROUTES)} flattened {PREFIX} "
        f"routes. Either the route was removed, or the flattening is broken — the self-checks "
        f"in TestRouterTableWasActuallyInspected distinguish the two."
    )

    shadowed = [
        f"{sorted(r.methods)} {r.path}"
        for r in AUDIT_ROUTES[catch_all_index + 1 :]
        if "{" not in r.path.removeprefix(PREFIX) and "GET" in r.methods
    ]
    assert not shadowed, (
        f"These literal GET routes are declared after {CATCH_ALL_PATH} and can never be "
        f"reached: {shadowed}. Move them above it."
    )
