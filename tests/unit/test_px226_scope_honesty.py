"""PX-226 / PX-225 honesty helpers for executive dashboard empty summaries."""

from src.api.schemas.executive_dashboard import ComplaintSummary, ExecutiveDashboardResponse, IncidentSummary, TrendData
from src.domain.services.executive_dashboard import (
    _EMPTY_COMPLAINT_SUMMARY,
    _EMPTY_INCIDENT_SUMMARY,
    _EMPTY_TRENDS,
    _TREND_SERIES,
)


def test_empty_incident_register_fields_are_none_not_zero():
    summary = IncidentSummary.model_validate(_EMPTY_INCIDENT_SUMMARY)
    assert summary.register_total is None
    assert summary.register_open is None
    assert summary.register_closed is None
    assert summary.avg_resolution_days is None


def test_empty_complaint_register_fields_are_none_not_zero():
    summary = ComplaintSummary.model_validate(_EMPTY_COMPLAINT_SUMMARY)
    assert summary.register_total is None
    assert summary.received_in_period_closed is None
    assert summary.avg_resolution_days is None
    assert summary.compliments_in_period == 0
    assert summary.compliment_to_complaint_ratio is None


def test_register_triple_reconciles_when_present():
    summary = IncidentSummary(
        total_in_period=5,
        open=3,
        by_severity={},
        sif_count=0,
        psif_count=0,
        critical_high=0,
        register_total=40,
        register_open=15,
        register_closed=25,
    )
    assert summary.register_open + summary.register_closed == summary.register_total


def test_empty_trends_marks_all_series_unavailable():
    trends = TrendData.model_validate(_EMPTY_TRENDS)
    assert set(trends.unavailable) == set(_TREND_SERIES)
    assert trends.incidents_weekly == []


def test_executive_dashboard_response_accepts_new_fields():
    """Smoke: additive fields still validate through the full response model."""
    from src.domain.services.executive_dashboard import (
        _EMPTY_AUDIT_SUMMARY,
        _EMPTY_COMPLIANCE_SUMMARY,
        _EMPTY_KRI_SUMMARY,
        _EMPTY_NEAR_MISS_SUMMARY,
        _EMPTY_RISK_SUMMARY,
        _EMPTY_RTA_SUMMARY,
        _EMPTY_SLA_SUMMARY,
    )

    payload = {
        "generated_at": "2026-07-26T00:00:00+00:00",
        "period_days": 30,
        "health_score": {
            "score": None,
            "status": "not_measured",
            "color": "grey",
            "components": {
                "incidents": 100.0,
                "near_miss_culture": 0.0,
                "risk_management": None,
                "kri_performance": None,
                "compliance": None,
                "sla_performance": None,
            },
        },
        "incidents": dict(_EMPTY_INCIDENT_SUMMARY),
        "near_misses": dict(_EMPTY_NEAR_MISS_SUMMARY),
        "complaints": dict(_EMPTY_COMPLAINT_SUMMARY),
        "rtas": dict(_EMPTY_RTA_SUMMARY),
        "risks": dict(_EMPTY_RISK_SUMMARY),
        "kris": dict(_EMPTY_KRI_SUMMARY),
        "compliance": dict(_EMPTY_COMPLIANCE_SUMMARY),
        "sla_performance": dict(_EMPTY_SLA_SUMMARY),
        "audits": dict(_EMPTY_AUDIT_SUMMARY),
        "trends": dict(_EMPTY_TRENDS),
        "alerts": [],
    }
    validated = ExecutiveDashboardResponse.model_validate(payload)
    assert validated.incidents.register_total is None
    assert "incidents_weekly" in validated.trends.unavailable
