"""Regression coverage for the mounted LOLER inspection-history route."""

from __future__ import annotations


def test_loler_inspection_history_is_mounted_on_api_router() -> None:
    from src.api import router

    paths = {route.path for route in router.routes if getattr(route, "path", None)}

    assert "/assets/{asset_id}/inspection-history" in paths
