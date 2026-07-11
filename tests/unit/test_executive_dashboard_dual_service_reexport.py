"""Path-to-10: src.services.executive_dashboard is a dual-service re-export."""

from src.domain.services import executive_dashboard as domain_mod
from src.services import executive_dashboard as services_mod


def test_executive_dashboard_services_reexport_domain_classes():
    assert services_mod.ExecutiveDashboardService is domain_mod.ExecutiveDashboardService


def test_executive_dashboard_accepts_optional_tenant_id():
    class _DummySession:
        pass

    svc = services_mod.ExecutiveDashboardService(_DummySession(), tenant_id=42)
    assert svc.tenant_id == 42
    assert svc._tenant_filter(type("M", (), {"tenant_id": object()})) is not True

    unscoped = services_mod.ExecutiveDashboardService(_DummySession())
    assert unscoped.tenant_id is None
    assert unscoped._tenant_filter(type("M", (), {"tenant_id": object()})) is True
