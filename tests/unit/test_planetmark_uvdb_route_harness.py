"""Planet Mark / UVDB route-registration harness (Wave C).

Lives under tests/unit so it does not depend on tests/e2e/conftest.py
autouse DB seeding (regulatory_updates.tenant_id). The e2e module
re-exports these assertions when the e2e seed environment is healthy.
"""

from __future__ import annotations


def _router_paths(router) -> set[str]:
    return {getattr(route, "path", "") for route in router.routes if getattr(route, "path", None)}


class TestPlanetMarkRouteHarness:
    def test_planet_mark_dashboard_route_registered(self):
        from src.api.routes.planet_mark import router

        paths = _router_paths(router)
        assert any(path.endswith("/dashboard") or path == "/dashboard" for path in paths)

    def test_planet_mark_years_route_registered(self):
        from src.api.routes.planet_mark import router

        paths = _router_paths(router)
        assert any("/years" in path for path in paths)


class TestUvdbRouteHarness:
    def test_uvdb_dashboard_route_registered(self):
        from src.api.routes.uvdb import router

        paths = _router_paths(router)
        assert any(path.endswith("/dashboard") or path == "/dashboard" for path in paths)

    def test_uvdb_sections_route_registered(self):
        from src.api.routes.uvdb import router

        paths = _router_paths(router)
        assert any("/sections" in path for path in paths)

    def test_uvdb_audits_route_registered(self):
        from src.api.routes.uvdb import router

        paths = _router_paths(router)
        assert any("/audits" in path for path in paths)

    def test_uvdb_iso_or_protocol_route_registered(self):
        from src.api.routes.uvdb import router

        paths = _router_paths(router)
        assert any("/iso-mapping" in path or "/protocol" in path for path in paths)

    def test_uvdb_protocol_export_route_registered(self):
        from src.api.routes.uvdb import router

        paths = _router_paths(router)
        assert any("/protocol/export" in path for path in paths)

    def test_uvdb_router_exposes_core_contract_surface(self):
        from src.api.routes.uvdb import router

        paths = _router_paths(router)
        assert any(path == "/audits" or path.endswith("/audits") for path in paths)
        assert any("/dashboard" in path for path in paths)
