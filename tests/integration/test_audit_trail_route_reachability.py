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
"""

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


def _resolve(method: str, path: str):
    """Return the route Starlette would dispatch to, mirroring its own scan order."""
    scope = {"type": "http", "method": method, "path": path, "headers": [], "root_path": ""}
    partial = None
    for route in app.routes:
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


@pytest.mark.parametrize("path", LITERAL_PATHS)
def test_literal_path_resolves_to_its_own_handler(path):
    """The literal route answers, not the ``/{entry_id}`` catch-all."""
    route = _resolve("GET", path)
    assert route is not None, f"GET {path} matched no route at all"
    assert route.path == path, (
        f"GET {path} is dispatched to {route.path} ({route.name}). "
        f"A path-parameter route declared earlier is shadowing it."
    )


@pytest.mark.parametrize("path", LITERAL_PATHS)
async def test_literal_path_is_not_swallowed_by_entry_id(admin_client, path):
    """Driving the real router must not yield the ``path -> entry_id`` 422."""
    response = await admin_client.get(path)
    assert not _is_entry_id_parse_error(response), (
        f"GET {path} returned the entry_id int-parsing 422, so it is being matched "
        f"as /{{entry_id}} and is unreachable. Body: {response.text}"
    )
    # Guard against the endpoint being unreachable for some other reason.
    assert response.status_code != 404, f"GET {path} returned 404: {response.text}"


async def test_entry_id_lookup_still_works(admin_client):
    """Reordering must not break the by-id route itself."""
    response = await admin_client.get(f"{PREFIX}/999999")
    assert not _is_entry_id_parse_error(response), response.text
    assert response.status_code == 404, f"expected a not-found for a missing entry, got {response.text}"

    route = _resolve("GET", f"{PREFIX}/999999")
    assert route is not None and route.path == CATCH_ALL_PATH


def test_no_audit_trail_literal_is_declared_after_the_catch_all():
    """Catch future literals added below ``/{entry_id}``, not just today's four.

    Registration order is what actually decides this, so assert on it directly
    rather than re-listing the paths we happen to know about.
    """
    audit_routes = [r for r in app.routes if getattr(r, "path", "").startswith(PREFIX) and getattr(r, "methods", None)]
    catch_all_index = next(
        (i for i, r in enumerate(audit_routes) if r.path == CATCH_ALL_PATH and "GET" in r.methods),
        None,
    )
    assert catch_all_index is not None, f"{CATCH_ALL_PATH} is no longer registered; update this test"

    shadowed = [
        f"{sorted(r.methods)} {r.path}"
        for r in audit_routes[catch_all_index + 1 :]
        if "{" not in r.path.removeprefix(PREFIX) and "GET" in r.methods
    ]
    assert not shadowed, (
        f"These literal GET routes are declared after {CATCH_ALL_PATH} and can never be "
        f"reached: {shadowed}. Move them above it."
    )
