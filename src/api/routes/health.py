"""Health sub-routes exposed under /api/v1/health."""

from fastapi import APIRouter

from src.infrastructure.resilience.circuit_breaker import get_all_circuits

router = APIRouter(prefix="/health")


@router.get("/circuits")
async def get_circuit_breaker_status():
    """Return the state and metrics of every registered circuit breaker."""
    circuits = get_all_circuits()
    return {
        "circuits": [cb.get_health() for cb in circuits],
        "total": len(circuits),
    }
