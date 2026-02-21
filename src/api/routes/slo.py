"""SLO/SLI metrics endpoint."""

from fastapi import APIRouter

from src.api.dependencies import CurrentSuperuser

router = APIRouter()


@router.get("/slo/current")
async def get_slo_metrics(current_user: CurrentSuperuser):
    """Get current SLO compliance metrics.

    Returns placeholder values that establish the API contract.
    Wire to live data sources (Azure Monitor, OpenTelemetry) in a future iteration.
    """
    return {
        "slos": [
            {
                "name": "API Availability",
                "target": 99.9,
                "current": 99.95,
                "window": "30d",
                "budget_remaining_pct": 50.0,
            },
            {
                "name": "API Latency P95",
                "target_ms": 500,
                "current_ms": 320,
                "window": "30d",
                "within_budget": True,
            },
            {
                "name": "Error Rate",
                "target_pct": 0.1,
                "current_pct": 0.05,
                "window": "30d",
                "within_budget": True,
            },
            {
                "name": "Deployment Success",
                "target_pct": 95.0,
                "current_pct": 100.0,
                "window": "90d",
                "within_budget": True,
            },
            {
                "name": "Background Task Reliability",
                "target_failure_pct": 1.0,
                "current_failure_pct": 0.3,
                "window": "30d",
                "within_budget": True,
            },
            {
                "name": "Cache Effectiveness",
                "target_hit_pct": 80.0,
                "current_hit_pct": 87.0,
                "window": "30d",
                "within_budget": True,
            },
        ]
    }
