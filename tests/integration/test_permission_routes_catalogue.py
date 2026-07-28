"""Cross-check the permission catalogue against the routes the app really serves.

The static AST scan in ``tests/unit/test_permission_catalogue.py`` reads source
text. This walks the dependency graph of the routes actually mounted on the app
and reads the token ``require_permission`` stamps on each checker. Two
independent extractors, because neither sees everything: the static scan sees the
in-handler ``has_permission`` calls that no dependency-graph walk can, and this
sees anything wired up by means a source scan cannot follow — a router-level
``dependencies=[...]``, a loop over a table of routes, a factory in another
module. A disagreement means one of them is lying.

Why this lives in the integration suite
---------------------------------------
Importing ``src.main`` opens a database engine at import time. This suite's
conftest calls ``assert_test_database_is_local`` before that happens, so the app
can be imported here without any risk of pointing an engine at a live
deployment. A unit test would carry no such guarantee. The mechanics of the walk
itself need none of this and are pinned separately, without an app, in
``tests/unit/test_permission_route_walk.py``.

The floor below is not decoration. On the first CI run this file reported 6
routes instead of 980 and refused to compare two near-empty sets. The cause was
not the app: it was ``include_router`` no longer flattening its routes onto
``app.routes`` in FastAPI 0.140, so a flat loop saw only what was declared
directly on the app. The walk now descends, and the unit tests named above fail
loudly and in seconds if that shape changes again.
"""

from __future__ import annotations

import pytest

from src.domain.authz.catalogue import ENFORCED_PERMISSIONS
from src.domain.authz.extraction import scan_source_tree, tokens_from_registered_routes

#: A floor, not an expected value: far below the real count so ordinary growth
#: never trips it, while an app that is not really mounted does.
MIN_REGISTERED_ROUTES = 500


@pytest.fixture(scope="module")
def route_scan():
    # Imported here rather than inside the extractor: src/domain may not depend on
    # src/api (scripts/check_import_boundaries.py enforces it), so wiring the app
    # into the walk is the caller's job.
    from src.main import app

    return tokens_from_registered_routes(app)


@pytest.fixture(scope="module")
def source_scan():
    return scan_source_tree()


def test_the_app_is_actually_mounted(route_scan):
    """Without this, every comparison below passes by comparing nothing."""
    assert route_scan.route_count >= MIN_REGISTERED_ROUTES, (
        f"only {route_scan.route_count} routes with a dependency graph were found. The app is not "
        "fully mounted, so this file's cross-checks would be vacuous rather than passing."
    )
    assert route_scan.token_set, "no permission tokens found on any mounted route"


def test_no_permission_checker_on_a_live_route_is_untagged(route_scan):
    """An untagged checker is enforcement this cross-check cannot see."""
    assert not route_scan.untagged_checkers, (
        "permission checkers on live routes with no __qgp_required_permission__ tag: "
        f"{route_scan.untagged_checkers}. Anything building a permission dependency must tag it, "
        "or this cross-check silently stops seeing it."
    )


def test_routes_enforce_only_catalogued_tokens(route_scan):
    uncatalogued = sorted(route_scan.token_set - ENFORCED_PERMISSIONS)
    assert not uncatalogued, (
        f"mounted routes enforce {uncatalogued}, which src/domain/authz/catalogue.py does not "
        "list. No role can be granted them, so those routes are unreachable for everyone except "
        "a superuser."
    )


def test_route_tokens_and_static_scan_agree(route_scan, source_scan):
    """The two extractors must see the same ``require_permission`` vocabulary."""
    only_on_routes = sorted(route_scan.token_set - source_scan.require_permission_tokens)
    assert not only_on_routes, (
        f"{only_on_routes} are enforced on mounted routes but the static scan did not find them. "
        "Something is wiring permissions in a way a source scan cannot read, which means the "
        "unit-level catalogue guard is blind to it."
    )

    only_in_source = sorted(source_scan.require_permission_tokens - route_scan.token_set)
    assert not only_in_source, (
        f"{only_in_source} appear in require_permission calls but on no mounted route. Either the "
        "router is not included in the app, or the route was deleted and the call site left behind."
    )
