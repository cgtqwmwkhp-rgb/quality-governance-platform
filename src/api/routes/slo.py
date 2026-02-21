"""SLO/SLI metrics endpoint with real in-memory metrics collection."""

import bisect
import threading
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

router = APIRouter()

_WINDOW_SECONDS = 30 * 24 * 3600  # 30-day rolling window


class _MetricsCollector:
    """Thread-safe in-memory collector for request latency and outcomes."""

    def __init__(self, max_samples: int = 100_000) -> None:
        self._lock = threading.Lock()
        self._max_samples = max_samples
        self._latencies: deque[tuple[float, float]] = deque(maxlen=max_samples)
        self._total_requests: int = 0
        self._failed_requests: int = 0

    def record(self, latency_s: float, *, success: bool) -> None:
        now = time.monotonic()
        with self._lock:
            self._latencies.append((now, latency_s))
            self._total_requests += 1
            if not success:
                self._failed_requests += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = self._total_requests
            failed = self._failed_requests
            sorted_latencies = sorted(v for _, v in self._latencies)

        successful = total - failed
        availability = (successful / total * 100) if total > 0 else 100.0
        budget_target = 99.9
        error_budget_total = (100.0 - budget_target) / 100.0 * total if total else 0
        errors_used = failed
        budget_remaining_pct = (
            ((error_budget_total - errors_used) / error_budget_total * 100) if error_budget_total > 0 else 100.0
        )

        p50 = _percentile(sorted_latencies, 0.50)
        p95 = _percentile(sorted_latencies, 0.95)
        p99 = _percentile(sorted_latencies, 0.99)

        error_rate = (failed / total * 100) if total > 0 else 0.0

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "availability_pct": round(availability, 4),
            "budget_remaining_pct": round(budget_remaining_pct, 2),
            "latency_p50_ms": round(p50 * 1000, 2),
            "latency_p95_ms": round(p95 * 1000, 2),
            "latency_p99_ms": round(p99 * 1000, 2),
            "error_rate_pct": round(error_rate, 4),
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = pct * (len(sorted_values) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = idx - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


metrics_collector = _MetricsCollector()


class SLOMetricsMiddleware(BaseHTTPMiddleware):
    """Records per-request latency and success/failure for SLO calculation."""

    SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/healthz", "/readyz")

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start

        success = response.status_code < 500
        metrics_collector.record(elapsed, success=success)
        return response


@router.get("/slo/current")
async def get_slo_metrics():
    """Get current SLO compliance metrics computed from live request data."""
    snap = metrics_collector.snapshot()
    return {
        "slos": [
            {
                "name": "API Availability",
                "target": 99.9,
                "current": snap["availability_pct"],
                "window": "30d",
                "budget_remaining_pct": snap["budget_remaining_pct"],
            },
            {
                "name": "API Latency P95",
                "target_ms": 500,
                "current_ms": snap["latency_p95_ms"],
                "window": "30d",
                "within_budget": snap["latency_p95_ms"] <= 500,
            },
            {
                "name": "Error Rate",
                "target_pct": 0.1,
                "current_pct": snap["error_rate_pct"],
                "window": "30d",
                "within_budget": snap["error_rate_pct"] <= 0.1,
            },
        ],
    }


@router.get("/slo/metrics")
async def get_slo_raw_metrics():
    """Expose raw SLO metrics snapshot (availability, latency percentiles)."""
    return metrics_collector.snapshot()
