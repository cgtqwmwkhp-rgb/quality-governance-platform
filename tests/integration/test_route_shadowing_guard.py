"""Repository-wide guard: no registered route may be shadowed into unreachability.

FastAPI matches routes in declaration order and takes the first FULL match. A
``@router.get("/{some_id}")`` declared before a ``@router.get("/literal")`` on the
same router therefore answers ``GET /literal``, tries to coerce ``"literal"`` into
the path parameter's type, and rejects the request — an HTTP 422 with a
``path -> <param>`` ``int_parsing`` error where the parameter is an ``int``.

The endpoint stays in the OpenAPI document the whole time, so neither the schema
snapshot (``openapi-baseline.json``) nor the contract suite notices. Nine live
instances of this were found across four routers by sweeping the router table;
finding them one at a time was not working, which is why this guard exists.

The guard resolves every registered route through the *real* matcher rather than
re-implementing Starlette's path semantics: it flattens the router tree into the
order the matcher scans, builds an HTTP scope, and walks the list calling
``route.matches(scope)`` exactly as ``Router.app`` does. Whatever answers first is
what production answers. That also means it needs no maintained list of known
paths — registration order is the thing that decides this, so it is what gets
asserted.

Two properties of the matcher this guard deliberately does *not* flag, because
neither is a defect:

* **Different segment counts cannot collide.** ``GET /read-logs/user/{user_id}``
  has three segments and is untouchable by a single-segment ``/{ack_id}``.
* **A method mismatch is only a PARTIAL match.** Starlette records the partial
  and keeps scanning, so ``POST /check-overdue`` declared after
  ``GET /{ack_id}`` still reaches its own handler.

Known-pending gaps live in ``PENDING_SHADOWED_ROUTES`` below, following the
baseline precedent set by PR #1387 in ``tests/contract/``: the active test fails
on anything *new*, and each pending entry is additionally asserted as an xfail so
a fix surfaces as XPASS instead of sitting in the list forever.
"""

from __future__ import annotations

import re
from typing import Iterable, Iterator

import pytest
from starlette.routing import Match

from src.main import app

# ---------------------------------------------------------------------------
# Pending list — REMOVE WHEN PR #1394 MERGES
# ---------------------------------------------------------------------------
#
# These four ``/api/v1/audit-trail`` routes are shadowed by ``GET /{entry_id}``
# on this branch and are NOT fixed here: the fix is PR #1394, which owns
# ``src/api/routes/audit_trail.py``. Editing that file from this branch would
# only create a merge conflict.
#
# This list exists so CI stays green while #1394 is in flight WITHOUT letting a
# new instance of the defect join silently — the active test below fails on any
# shadowed route that is not exactly one of these.
#
# ==> WHOEVER MERGES PR #1394: delete this list and the two tests that reference
# ==> it (``test_pending_audit_trail_routes_are_fixed_by_pr_1394`` and the
# ==> ``PENDING_SHADOWED_ROUTES`` argument to the active test). The xfail entries
# ==> will start reporting XPASS the moment #1394 lands, which is the signal.
PENDING_SHADOWED_ROUTES: frozenset[str] = frozenset(
    {
        "GET /api/v1/audit-trail/actions",
        "GET /api/v1/audit-trail/entity-types",
        "GET /api/v1/audit-trail/stats",
        "GET /api/v1/audit-trail/verifications",
    }
)

_PENDING_PREFIX = "/api/v1/audit-trail/"

# Values substituted for path parameters so a parameterised route can be probed.
# The default is deliberately something no literal segment uses, so probing a
# parameterised route cannot collide with a real literal and report a false
# shadow. Typed convertors (``{investigation_id:int}``) constrain the segment
# regex, so the probe has to satisfy the convertor or the route will not match
# its own path — keyed on the convertor class so a newly used type is obvious.
_DEFAULT_PARAM_PROBE = "__shadow_probe__"
_PROBE_BY_CONVERTOR: dict[str, str] = {
    "IntegerConvertor": "424242",
    "FloatConvertor": "424242.5",
    "UUIDConvertor": "00000000-0000-0000-0000-000000000042",
}

_PARAM_RE = re.compile(r"\{(?P<name>[^}:]+)(?::[^}]+)?\}")


def _probe_path(route: object) -> str:
    """Concrete path that should reach ``route`` and nothing declared before it."""
    convertors = getattr(route, "param_convertors", None) or {}

    def substitute(match: re.Match[str]) -> str:
        convertor = convertors.get(match.group("name"))
        return _PROBE_BY_CONVERTOR.get(type(convertor).__name__, _DEFAULT_PARAM_PROBE)

    return _PARAM_RE.sub(substitute, route.path)


# HEAD and OPTIONS are synthesised by the framework and share a path with their
# GET/CORS counterparts, so resolving them says nothing about reachability.
_SYNTHETIC_METHODS = frozenset({"HEAD", "OPTIONS"})


# ---------------------------------------------------------------------------
# Flattening the router tree into matcher scan order
# ---------------------------------------------------------------------------


def _iter_scan_order(routes: Iterable[object]) -> Iterator[object]:
    """Flatten the router tree into the order the matcher actually scans it.

    FastAPI >= 0.140 keeps included routers nested under ``_IncludedRouter``
    instead of flattening them into ``app.routes``. Its ``_match`` walks those
    candidates in declaration order and recurses depth-first, which is exactly
    what this reproduces. ``effective_route_contexts`` is duck-typed rather than
    isinstance-checked so this keeps working on the older flat representation.
    """
    for route in routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from contexts()
        else:
            yield route


SCAN_ORDER: list[object] = list(_iter_scan_order(app.routes))
HTTP_ROUTES: list[object] = [
    route for route in SCAN_ORDER if getattr(route, "methods", None) and getattr(route, "path", None)
]


def _scope(method: str, path: str) -> dict[str, object]:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "root_path": "",
    }


def _resolve(method: str, path: str) -> object | None:
    """Return the route Starlette would dispatch to, mirroring ``Router.app``.

    First FULL match wins; a PARTIAL (path matched, method did not) is held aside
    and only used if nothing fully matches.
    """
    scope = _scope(method, path)
    partial = None
    for route in SCAN_ORDER:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
        if match == Match.PARTIAL and partial is None:
            partial = route
    return partial


def _label(method: str, path: str) -> str:
    return f"{method} {path}"


def _sweep() -> tuple[dict[str, str], list[str]]:
    """Resolve every registered route and report the unreachable ones.

    Returns ``(shadowed, unprobeable)``. ``unprobeable`` holds routes whose probe
    path does not even match the route itself — that means the probe generator
    is wrong (an unhandled convertor type), not that the route is dead, and it is
    reported separately so it can never be mistaken for a shadowing defect.
    """
    shadowed: dict[str, str] = {}
    unprobeable: list[str] = []
    for route in HTTP_ROUTES:
        path = route.path
        probe = _probe_path(route)
        for method in sorted(route.methods):
            if method in _SYNTHETIC_METHODS:
                continue
            scope = _scope(method, probe)
            own_match, _ = route.matches(scope)
            if own_match != Match.FULL:
                unprobeable.append(f"{_label(method, path)} (probe {probe!r})")
                continue
            winner = _resolve(method, probe)
            if winner is not None and winner.path != path:
                shadowed[_label(method, path)] = f"{winner.path} ({getattr(winner, 'name', '?')})"
    return shadowed, unprobeable


SHADOWED_ROUTES, UNPROBEABLE_ROUTES = _sweep()


# ---------------------------------------------------------------------------
# Self-check
#
# A sweep-based guard fails open: if the flattening returns nothing, every test
# below passes while checking nothing. That is precisely how the OpenAPI contract
# suite missed all nine of these. Assert the sweep saw a real router table first.
# ---------------------------------------------------------------------------


class TestSweepIsNotVacuous:
    def test_sweep_sees_the_whole_router_table(self) -> None:
        assert len(HTTP_ROUTES) > 500, (
            f"Only {len(HTTP_ROUTES)} HTTP routes were flattened out of the app. The router "
            f"tree representation has changed and _iter_scan_order no longer walks it, so every "
            f"assertion in this module is passing vacuously."
        )

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/document-control/summary"),
            ("GET", "/api/v1/evidence-assets/download"),
            ("GET", "/api/v1/policy-acknowledgments/dashboard"),
            ("GET", "/api/v1/audit-trail/stats"),
        ],
    )
    def test_known_routes_are_present_in_the_sweep(self, method: str, path: str) -> None:
        """Anchor the sweep on paths that must exist, so a silent drop is caught."""
        assert any(
            route.path == path and method in route.methods for route in HTTP_ROUTES
        ), f"{method} {path} is not in the flattened router table"

    def test_the_matcher_resolves_an_unambiguous_route_to_itself(self) -> None:
        """Sanity-check ``_resolve`` itself against a route nothing can shadow."""
        winner = _resolve("GET", "/health")
        assert winner is not None and winner.path == "/health"

    def test_every_route_can_be_probed(self) -> None:
        """A route that will not match its own probe is skipped by the sweep.

        That is a hole in the guard, not a defect in the route — it means a path
        convertor is in use that ``_PROBE_BY_CONVERTOR`` does not know how to
        satisfy, so those routes are silently excluded from shadow detection.
        """
        assert not UNPROBEABLE_ROUTES, (
            "The probe generator could not build a path that reaches these routes, so they were "
            "excluded from the shadowing sweep. Add their path convertor to _PROBE_BY_CONVERTOR:\n"
            + "\n".join(f"  {entry}" for entry in sorted(UNPROBEABLE_ROUTES))
        )


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class TestNoRouteIsShadowed:
    def test_no_registered_route_is_unreachable(self) -> None:
        """No route may be answered by a different route declared above it."""
        unexpected = {
            label: winner for label, winner in SHADOWED_ROUTES.items() if label not in PENDING_SHADOWED_ROUTES
        }
        assert not unexpected, (
            "These registered routes can never be reached — a route declared earlier in the "
            "same router matches their path first, so requests are answered by it (typically a "
            "422 'path -> <param>' int-parsing error) while the endpoint still appears in the "
            "OpenAPI document:\n"
            + "\n".join(
                f"  {label}\n      answered instead by {winner}" for label, winner in sorted(unexpected.items())
            )
            + "\n\nFix by moving the path-parameter route below every literal on its router. "
            "Do not add entries to PENDING_SHADOWED_ROUTES for new work — that list is a "
            "cross-branch handover for PR #1394 only."
        )

    def test_no_duplicate_route_registration(self) -> None:
        """The other way to register a dead route: the same method+path twice.

        The second registration is unreachable for the same reason. Currently
        zero, so this is a gate rather than a backlog.
        """
        seen: dict[str, int] = {}
        for route in HTTP_ROUTES:
            for method in sorted(route.methods):
                if method in _SYNTHETIC_METHODS:
                    continue
                label = _label(method, route.path)
                seen[label] = seen.get(label, 0) + 1
        duplicates = {label: count for label, count in seen.items() if count > 1}
        assert not duplicates, (
            f"These method+path pairs are registered more than once; every registration after "
            f"the first is unreachable: {duplicates}"
        )

    @pytest.mark.parametrize("label", sorted(PENDING_SHADOWED_ROUTES))
    @pytest.mark.xfail(
        reason="Shadowed by GET /api/v1/audit-trail/{entry_id}; fixed by PR #1394, not by this branch",
        strict=False,
    )
    def test_pending_audit_trail_routes_are_fixed_by_pr_1394(self, label: str) -> None:
        """Goal state for the pending list — XPASS here means #1394 has landed.

        When all four XPASS, delete ``PENDING_SHADOWED_ROUTES`` and this test.
        """
        assert label not in SHADOWED_ROUTES, f"{label} is still shadowed by {SHADOWED_ROUTES.get(label)}"

    def test_pending_list_covers_only_the_audit_trail_handover(self) -> None:
        """Stop the pending list being used to park anything else."""
        strays = sorted(label for label in PENDING_SHADOWED_ROUTES if not label.startswith(f"GET {_PENDING_PREFIX}"))
        assert not strays, (
            f"PENDING_SHADOWED_ROUTES exists solely to hand the audit_trail.py routes to "
            f"PR #1394. These entries do not belong to it: {strays}"
        )


# ---------------------------------------------------------------------------
# The five routes this branch fixes — resolution plus real HTTP
# ---------------------------------------------------------------------------

# What each newly-reachable literal must answer, stated exactly.
#
# This started life as ``status_code != 404``, which was too weak: unshadowing
# ``/summary`` exposed a 500 behind it (an aware datetime bound against a naive
# column) and "not a 404" accepted that happily. A reachability test that tolerates
# a 500 is not measuring reachability, it is measuring routing — and routing is
# already covered by ``test_literal_resolves_to_its_own_handler`` without needing a
# request. The point of driving real HTTP is to prove the handler *runs*.
#
# Note what this suite structurally CANNOT check, so nobody reads a pass as more
# than it is: the integration harness calls ``Base.metadata.create_all``, so every
# model's table exists here whether or not a migration creates it. Seven
# document-control tables have no migration at all — ``document_approval_workflows``
# and ``document_distributions`` among them — so ``/workflows`` and ``/summary``
# return 200 here and 500 against a migrations-only database. That gap is real but
# it is migration drift, not route shadowing, and detecting it needs a database
# built by Alembic alone. See the PR discussion; it belongs with whoever owns
# ``alembic/``. Do not weaken the statuses below to paper over it.
EXPECTED_STATUS: dict[str, tuple[frozenset[int], str]] = {
    "/api/v1/document-control/summary": (
        frozenset({200}),
        "returns the document counts it exists to return",
    ),
    "/api/v1/document-control/workflows": (
        frozenset({200}),
        "returns the (possibly empty) list of approval workflows",
    ),
    "/api/v1/evidence-assets/download": (
        frozenset({422}),
        "its own signature requires key/expires/sig, so a bare GET is a query-level 422 — "
        "reaching that proves the handler answered rather than the by-id route",
    ),
    "/api/v1/policy-acknowledgments/dashboard": (
        frozenset({200}),
        "returns the compliance dashboard",
    ),
    "/api/v1/policy-acknowledgments/reminders-needed": (
        frozenset({200}),
        "returns the set of acknowledgments due a reminder",
    ),
}

FIXED_LITERALS = list(EXPECTED_STATUS)

# The by-id routes that were moved. Each must still answer its own path.
MOVED_CATCH_ALLS = [
    ("/api/v1/document-control/{document_id}", "/api/v1/document-control/999999", "document_id"),
    ("/api/v1/evidence-assets/{asset_id}", "/api/v1/evidence-assets/999999", "asset_id"),
    (
        "/api/v1/policy-acknowledgments/{acknowledgment_id}",
        "/api/v1/policy-acknowledgments/999999",
        "acknowledgment_id",
    ),
]


def _is_path_param_parse_error(response, param: str) -> bool:
    """True if this is the 422 produced by feeding a literal to an int path param."""
    if response.status_code != 422:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    errors = body.get("error", {}).get("details", {}).get("errors", [])
    if not isinstance(errors, list):
        return False
    return any(param in str(err.get("field", "")) and err.get("type") == "int_parsing" for err in errors)


class TestFixedRoutesAreReachable:
    @pytest.mark.parametrize("path", FIXED_LITERALS)
    def test_literal_resolves_to_its_own_handler(self, path: str) -> None:
        winner = _resolve("GET", path)
        assert winner is not None, f"GET {path} matched no route at all"
        assert winner.path == path, (
            f"GET {path} is dispatched to {winner.path} ({getattr(winner, 'name', '?')}). "
            f"A path-parameter route declared earlier is shadowing it."
        )

    @pytest.mark.parametrize("path", FIXED_LITERALS)
    async def test_literal_is_not_swallowed_over_http(self, admin_client, path: str) -> None:
        """Drive the real router — the schema-level checks cannot see this."""
        response = await admin_client.get(path)
        for _, _, param in MOVED_CATCH_ALLS:
            assert not _is_path_param_parse_error(response, param), (
                f"GET {path} returned the {param} int-parsing 422, so it is still being matched "
                f"as the by-id route and is unreachable. Body: {response.text}"
            )
        expected, because = EXPECTED_STATUS[path]
        assert response.status_code in expected, (
            f"GET {path} returned {response.status_code}; expected {sorted(expected)} because it "
            f"{because}. Reaching the handler is only half of it — the handler has to work. A 5xx "
            f"here means the endpoint was unreachable long enough for a defect to accumulate behind "
            f"it unnoticed; fix the handler rather than widening this expectation. "
            f"Body: {response.text}"
        )

    @pytest.mark.parametrize("route_path,probe,param", MOVED_CATCH_ALLS)
    def test_moved_by_id_route_still_owns_its_path(self, route_path: str, probe: str, param: str) -> None:
        winner = _resolve("GET", probe)
        assert winner is not None and winner.path == route_path, (
            f"GET {probe} now resolves to {getattr(winner, 'path', None)}, not {route_path}. "
            f"The move broke the by-id lookup."
        )

    @pytest.mark.parametrize("route_path,probe,param", MOVED_CATCH_ALLS)
    async def test_moved_by_id_route_still_works_over_http(
        self, admin_client, route_path: str, probe: str, param: str
    ) -> None:
        """Reordering must not break the by-id lookup: a missing row is a 404."""
        response = await admin_client.get(probe)
        assert not _is_path_param_parse_error(response, param), response.text
        assert (
            response.status_code == 404
        ), f"expected a not-found for a missing record at {probe}, got {response.status_code}: {response.text}"
