"""Executive dashboard must stay schema-valid when sub-queries fail."""

from datetime import datetime, timezone

import pytest

from src.api.schemas.executive_dashboard import ExecutiveDashboardResponse
from src.domain.services.executive_dashboard import (
    ExecutiveDashboardService,
    _EMPTY_COMPLAINT_SUMMARY,
    _EMPTY_INCIDENT_SUMMARY,
    _EMPTY_NEAR_MISS_SUMMARY,
    _EMPTY_RTA_SUMMARY,
    _EMPTY_TRENDS,
)


def test_empty_incident_summary_matches_response_schema():
    ExecutiveDashboardResponse.model_validate(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": 30,
            "health_score": {
                "score": 80.0,
                "status": "healthy",
                "color": "green",
                "components": {
                    "incidents": 80.0,
                    "near_miss_culture": 70.0,
                    "risk_management": 90.0,
                    "kri_performance": 85.0,
                    "compliance": 95.0,
                    "sla_performance": 88.0,
                },
            },
            "incidents": _EMPTY_INCIDENT_SUMMARY,
            "near_misses": _EMPTY_NEAR_MISS_SUMMARY,
            "complaints": _EMPTY_COMPLAINT_SUMMARY,
            "rtas": _EMPTY_RTA_SUMMARY,
            "risks": {
                "total_active": 0,
                "by_level": {},
                "high_critical": 0,
                "average_score": 0.0,
            },
            "kris": {
                "total_active": 0,
                "by_status": {"green": 0, "amber": 0, "red": 0, "not_measured": 0},
                "at_risk": 0,
                "pending_alerts": 0,
            },
            "compliance": {
                "total_assigned": 0,
                "completed": 0,
                "overdue": 0,
                "completion_rate": 100.0,
            },
            "sla_performance": {
                "total_tracked": 0,
                "met": 0,
                "breached": 0,
                "compliance_rate": 100.0,
            },
            "trends": _EMPTY_TRENDS,
            "alerts": [],
        }
    )


@pytest.mark.asyncio
async def test_get_full_dashboard_survives_failed_subqueries():
    class _FailingSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("simulated prod DB failure")

    service = ExecutiveDashboardService(_FailingSession(), tenant_id=7)
    payload = await service.get_full_dashboard(30)
    validated = ExecutiveDashboardResponse.model_validate(payload)
    assert validated.incidents.total_in_period == 0
    assert validated.near_misses.reporting_rate == "stable"
    assert validated.complaints.resolution_rate == 100.0
    assert validated.trends.incidents_weekly == []
