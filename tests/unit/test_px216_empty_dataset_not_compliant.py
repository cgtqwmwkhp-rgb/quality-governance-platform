"""PX-216 regression suite: an empty dataset must never report as 100%.

One test per site that previously divide-guarded a zero denominator to a
"fully compliant" number. Each asserts the value is ``None`` *and* explicitly
asserts it is not 100, because 100 is the specific lie being fixed.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.api.routes import slo as slo_module
from src.api.routes.executive_dashboard import get_vehicle_governance
from src.api.routes.vehicles import fleet_health
from src.domain.services.executive_dashboard import (
    _EMPTY_COMPLAINT_SUMMARY,
    _EMPTY_COMPLIANCE_SUMMARY,
    _EMPTY_INCIDENT_SUMMARY,
    _EMPTY_KRI_SUMMARY,
    _EMPTY_NEAR_MISS_SUMMARY,
    _EMPTY_RISK_SUMMARY,
    _EMPTY_SLA_SUMMARY,
    ExecutiveDashboardService,
)


class _EmptyResult:
    """Mimics a SQLAlchemy Result over a table with no matching rows."""

    def scalar(self):
        return 0

    def all(self):
        return []

    def scalars(self):
        return self

    def first(self):
        return None


class _EmptyDbSession:
    async def execute(self, *_args, **_kwargs):
        return _EmptyResult()


_USER = SimpleNamespace(id=1, tenant_id=1)
_CUTOFF = datetime.now(timezone.utc) - timedelta(days=30)


# ---------------------------------------------------------------------------
# src/domain/services/executive_dashboard.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complaint_resolution_rate_is_not_measured_when_no_complaints():
    service = ExecutiveDashboardService(_EmptyDbSession(), tenant_id=1)
    summary = await service._get_complaint_summary(cutoff=_CUTOFF)

    assert summary["total_in_period"] == 0
    assert summary["resolution_rate"] is None
    assert summary["resolution_rate"] != 100


@pytest.mark.asyncio
async def test_policy_completion_rate_is_not_measured_when_nothing_assigned():
    service = ExecutiveDashboardService(_EmptyDbSession(), tenant_id=1)
    summary = await service._get_compliance_summary()

    assert summary["total_assigned"] == 0
    assert summary["completion_rate"] is None
    assert summary["completion_rate"] != 100


@pytest.mark.asyncio
async def test_sla_compliance_rate_is_not_measured_when_nothing_tracked():
    service = ExecutiveDashboardService(_EmptyDbSession(), tenant_id=1)
    summary = await service._get_sla_summary()

    assert summary["total_tracked"] == 0
    assert summary["compliance_rate"] is None
    assert summary["compliance_rate"] != 100


def test_health_score_drops_unmeasured_components_instead_of_scoring_them_100():
    service = ExecutiveDashboardService(_EmptyDbSession(), tenant_id=1)

    health = service._calculate_health_score(
        dict(_EMPTY_INCIDENT_SUMMARY),
        dict(_EMPTY_NEAR_MISS_SUMMARY),
        dict(_EMPTY_COMPLAINT_SUMMARY),
        dict(_EMPTY_RISK_SUMMARY),
        dict(_EMPTY_KRI_SUMMARY),
        dict(_EMPTY_COMPLIANCE_SUMMARY),
        dict(_EMPTY_SLA_SUMMARY),
    )

    components = health["components"]
    assert components["risk_management"] is None
    assert components["kri_performance"] is None
    assert components["compliance"] is None
    assert components["sla_performance"] is None

    # Only incidents (100, weight 20) and near-miss culture (0, weight 10) are
    # measurable from an empty org, so the score is their weighted average — not
    # the 90.0 the old code produced by scoring four empty registers 100 each.
    assert health["score"] == pytest.approx(66.7, abs=0.05)
    assert health["status"] == "attention_needed"


# ---------------------------------------------------------------------------
# src/api/routes/executive_dashboard.py + src/api/routes/vehicles.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vehicle_governance_compliance_rate_is_not_measured_for_empty_fleet():
    summary = await get_vehicle_governance(db=_EmptyDbSession(), current_user=_USER)

    assert summary.total_vehicles == 0
    assert summary.compliance_rate is None
    assert summary.compliance_rate != 100


@pytest.mark.asyncio
async def test_fleet_health_compliance_rate_is_not_measured_for_empty_registry():
    response = await fleet_health(db=_EmptyDbSession(), user=_USER)

    assert response.total_vehicles == 0
    assert response.compliance_rate is None
    assert response.compliance_rate != 100


# ---------------------------------------------------------------------------
# src/api/routes/slo.py
# ---------------------------------------------------------------------------


def test_slo_snapshot_reports_no_data_before_any_traffic():
    snapshot = slo_module._MetricsCollector().snapshot()

    assert snapshot["total_requests"] == 0
    assert snapshot["availability_pct"] is None
    assert snapshot["availability_pct"] != 100
    assert snapshot["budget_remaining_pct"] is None
    assert snapshot["error_rate_pct"] is None
    assert snapshot["latency_p99_ms"] is None


def test_slo_snapshot_reports_real_availability_once_traffic_exists():
    collector = slo_module._MetricsCollector()
    for _ in range(3):
        collector.record(0.01, status_code=200)
    collector.record(0.02, status_code=500)

    snapshot = collector.snapshot()
    assert snapshot["availability_pct"] == 75.0
    assert snapshot["error_rate_pct"] == 25.0
    assert snapshot["latency_p99_ms"] is not None


def test_health_check_availability_is_not_measured_before_any_probe():
    availability = slo_module._HealthCheckTracker().availability()

    assert availability["total_checks"] == 0
    assert availability["availability_pct"] is None
    assert availability["availability_pct"] != 100


@pytest.mark.asyncio
async def test_slo_current_endpoint_reports_no_data_without_crashing(monkeypatch):
    monkeypatch.setattr(slo_module, "metrics_collector", slo_module._MetricsCollector())
    monkeypatch.setattr(slo_module, "health_tracker", slo_module._HealthCheckTracker())

    payload = await slo_module.get_slo_metrics()
    by_name = {entry["name"]: entry for entry in payload["slos"]}

    assert by_name["API Availability"]["current"] is None
    assert by_name["API Latency P99"]["within_budget"] is None
    assert by_name["Error Rate"]["within_budget"] is None
    assert by_name["Health Check Availability"]["current"] is None
