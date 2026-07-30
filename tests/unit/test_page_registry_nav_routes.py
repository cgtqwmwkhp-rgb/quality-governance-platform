"""Governance check: Layout nav targets must appear in PAGE_REGISTRY for link audit."""

from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY_PATH = Path("docs/ops/PAGE_REGISTRY.yml")

# UX gate run 30523733146 — "Route not in registry" false positives from Layout nav.
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
)


def _admin_routes_by_path() -> dict[str, dict]:
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    return {entry["route"]: entry for entry in data.get("admin_routes", [])}


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
