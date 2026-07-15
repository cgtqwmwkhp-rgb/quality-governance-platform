"""Regression coverage for the mounted LOLER inspection-history route."""

from __future__ import annotations

from pathlib import Path


def test_loler_inspection_history_route_is_registered() -> None:
    """Avoid importing the aggregate API router (heavy/CI-fragile); assert mount in source + route module."""
    from src.api.routes import loler_inspections

    module_paths = {
        path for route in loler_inspections.router.routes if isinstance((path := getattr(route, "path", None)), str)
    }
    assert "/assets/{asset_id}/inspection-history" in module_paths

    api_init = Path("src/api/__init__.py").read_text(encoding="utf-8")
    assert "loler_inspections," in api_init
    assert "include_router(loler_inspections.router" in api_init
