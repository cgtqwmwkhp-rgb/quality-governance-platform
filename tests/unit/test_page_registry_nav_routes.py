"""Governance check: Layout nav targets must appear in PAGE_REGISTRY for link audit."""

from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY_PATH = Path("docs/ops/PAGE_REGISTRY.yml")

# UX gate run 30523733146 — "Route not in registry" false positives from Layout nav.
# Extended after #1446/#1448 for the residual Layout admin + competence-gaps targets
# that App.tsx mounts and Layout still linked while PAGE_REGISTRY omitted them.
LAYOUT_NAV_ROUTES = (
    "/safety-assets",
    "/customer-audits",
    "/my-reading",
    "/my-compliance",
    "/analytics/hs-performance",
    "/analytics/safety-insights",
    "/knowledge-exceptions",
    "/document-control",
    # Linked from HsPerformance + Layout admin nav; last dead end on tip 375f078a.
    "/admin/hs-reporting-hours",
    # C-61 residual on tip faff5a38 — Layout admin nav + workforce hub.
    "/admin/users",
    "/admin/lookups",
    "/admin/hseq-inbox",
    "/admin/notifications",
    "/admin/partner-webhooks",
    "/workforce/competence-gaps",
)

# AdminDashboard tiles / hub deep-links that are not always in Layout nav but are
# real App.tsx routes the link audit will walk from /admin and asset-health tiles.
ADMIN_DASHBOARD_AND_HUB_ROUTES = (
    "/admin/library-roles",
    "/admin/engineer-groups",
    "/safety-assets/analytics",
)

<<<<<<< HEAD
# App.tsx <Navigate replace> legacy staff aliases (golden-thread UAT). Canonical
# targets are already registered; these P2 entries keep bookmark/compat paths off
# the "Route not in registry" dead-end list. Parallel to #1484 (portal pages).
NAVIGATE_ALIAS_ROUTES = (
    "/capa",
    "/my-work",
    "/evidence",
    "/knowledge-bank",
    "/exceptions",
    "/admin/campaign-compliance",
    "/admin/hsec-inbox",
=======
# Nested /portal children mounted under App.tsx path="/portal". Linked from Portal
# home, Dashboard, and My Day. #1451 residuals incorrectly called tools/van/work
# "real dead ends" after a flat App.tsx scrape missed nesting.
PORTAL_LINKED_ROUTES = (
    "/portal/work",
    "/portal/reading",
    "/portal/tools",
    "/portal/van",
    "/portal/track/:referenceNumber",
>>>>>>> origin/main
)


def _load_registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def _admin_routes_by_path() -> dict[str, dict]:
    return {entry["route"]: entry for entry in _load_registry().get("admin_routes", [])}
<<<<<<< HEAD
=======


def _portal_routes_by_path() -> dict[str, dict]:
    return {entry["route"]: entry for entry in _load_registry().get("portal_routes", [])}
>>>>>>> origin/main


def test_layout_nav_routes_registered_in_page_registry() -> None:
    by_route = _admin_routes_by_path()
    missing = [route for route in LAYOUT_NAV_ROUTES if route not in by_route]
    assert not missing, f"Missing PAGE_REGISTRY admin_routes entries: {missing}"


def test_layout_nav_routes_registered_as_staff_p1() -> None:
    by_route = _admin_routes_by_path()
    for route in LAYOUT_NAV_ROUTES:
        entry = by_route[route]
        assert entry["auth"] == "jwt_admin", route
        assert entry["criticality"] == "P1", route


def test_admin_dashboard_and_hub_routes_registered_in_page_registry() -> None:
    by_route = _admin_routes_by_path()
    missing = [route for route in ADMIN_DASHBOARD_AND_HUB_ROUTES if route not in by_route]
    assert not missing, f"Missing PAGE_REGISTRY admin_routes entries: {missing}"


def test_admin_dashboard_and_hub_routes_registered_as_staff_p1() -> None:
    by_route = _admin_routes_by_path()
    for route in ADMIN_DASHBOARD_AND_HUB_ROUTES:
        entry = by_route[route]
        assert entry["auth"] == "jwt_admin", route
        assert entry["criticality"] == "P1", route


<<<<<<< HEAD
def test_navigate_alias_routes_registered_in_page_registry() -> None:
    by_route = _admin_routes_by_path()
    missing = [route for route in NAVIGATE_ALIAS_ROUTES if route not in by_route]
    assert not missing, f"Missing PAGE_REGISTRY admin_routes alias entries: {missing}"


def test_navigate_alias_routes_registered_as_staff_p2() -> None:
    by_route = _admin_routes_by_path()
    for route in NAVIGATE_ALIAS_ROUTES:
        entry = by_route[route]
        assert entry["auth"] == "jwt_admin", route
        assert entry["criticality"] == "P2", route
        assert entry["component"] == "Navigate", route
=======
def test_portal_linked_routes_registered_in_page_registry() -> None:
    by_route = _portal_routes_by_path()
    missing = [route for route in PORTAL_LINKED_ROUTES if route not in by_route]
    assert not missing, f"Missing PAGE_REGISTRY portal_routes entries: {missing}"


def test_portal_linked_routes_registered_as_portal_sso_p1() -> None:
    by_route = _portal_routes_by_path()
    for route in PORTAL_LINKED_ROUTES:
        entry = by_route[route]
        assert entry["auth"] == "portal_sso", route
        assert entry["criticality"] == "P1", route
>>>>>>> origin/main


def test_page_registry_summary_matches_measured_counts() -> None:
    data = _load_registry()
    entries = []
    for section in ("public_routes", "portal_routes", "admin_routes"):
        entries.extend(data.get(section) or [])
    summary = data.get("summary") or {}
    assert summary.get("total_routes") == len(entries)
    assert summary.get("p0_routes") == sum(1 for e in entries if e.get("criticality") == "P0")
    assert summary.get("p1_routes") == sum(1 for e in entries if e.get("criticality") == "P1")
    assert summary.get("p2_routes") == sum(1 for e in entries if e.get("criticality") == "P2")
