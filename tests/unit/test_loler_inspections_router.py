"""Regression coverage for the mounted LOLER inspection-history route."""

from __future__ import annotations


def _collect_paths(routes) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
        nested = getattr(route, "routes", None)
        if nested is not None:
            paths |= _collect_paths(nested)
    return paths


def test_loler_inspection_history_is_mounted_on_api_router() -> None:
    from src.api import router
    from src.api.routes import loler_inspections

    paths = _collect_paths(router.routes)
    assert "/assets/{asset_id}/inspection-history" in paths
    # Also confirm the route module itself defines the expected path.
    module_paths = _collect_paths(loler_inspections.router.routes)
    assert "/assets/{asset_id}/inspection-history" in module_paths
