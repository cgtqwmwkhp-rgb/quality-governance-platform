"""SLO/SLI metrics endpoint with real in-memory metrics collection.

Tracks three core SLIs from live traffic:
  - Availability  – ratio of non-5xx responses to total responses
  - Latency P99   – computed from per-request durations captured by middleware
  - Error rate    – ratio of 5xx responses to total responses

Health-check availability is tracked separately so /healthz and /readyz
outcomes feed an independent availability signal.

All counters survive process restarts when Redis is available (best-effort
persistence; falls back to in-memory-only gracefully).
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

router = APIRouter()
logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 30 * 24 * 3600  # 30-day rolling window
_REDIS_KEY = "slo:metrics:v1"
_PERSIST_INTERVAL_S = 60  # flush to Redis at most every 60 s


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = pct * (len(sorted_values) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = idx - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


class _MetricsCollector:
    """Thread-safe in-memory collector for request latency and outcomes.

    Maintains a rolling window of individual latency samples and
    monotonic counters for total / failed requests.  Supports optional
    Redis persistence so counters survive restarts.
    """

    def __init__(self, max_samples: int = 100_000) -> None:
        self._lock = threading.Lock()
        self._max_samples = max_samples
        # (wall-clock timestamp, latency_seconds)
        self._latencies: deque[tuple[float, float]] = deque(maxlen=max_samples)
        self._total_requests: int = 0
        self._failed_requests: int = 0  # 5xx
        self._status_counts: dict[int, int] = {}  # status-code → count
        self._last_persist: float = 0.0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, latency_s: float, *, status_code: int) -> None:
        now = time.time()
        success = status_code < 500
        with self._lock:
            self._latencies.append((now, latency_s))
            self._total_requests += 1
            if not success:
                self._failed_requests += 1
            self._status_counts[status_code] = self._status_counts.get(status_code, 0) + 1

    # ------------------------------------------------------------------
    # Windowed snapshot
    # ------------------------------------------------------------------

    def _prune_old(self, cutoff: float) -> None:
        """Remove samples older than *cutoff* (wall-clock seconds)."""
        while self._latencies and self._latencies[0][0] < cutoff:
            self._latencies.popleft()

    def snapshot(self, window_seconds: int = _WINDOW_SECONDS) -> dict[str, Any]:
        cutoff = time.time() - window_seconds
        with self._lock:
            self._prune_old(cutoff)
            total = self._total_requests
            failed = self._failed_requests
            sorted_latencies = sorted(v for _, v in self._latencies)
            status_snapshot = dict(self._status_counts)

        successful = total - failed
        availability = (successful / total * 100) if total > 0 else 100.0

        budget_target = 99.9
        error_budget_total = (100.0 - budget_target) / 100.0 * total if total else 0
        budget_remaining_pct = (
            ((error_budget_total - failed) / error_budget_total * 100) if error_budget_total > 0 else 100.0
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
            "status_code_counts": status_snapshot,
            "window_seconds": window_seconds,
        }

    # ------------------------------------------------------------------
    # Redis persistence (best-effort)
    # ------------------------------------------------------------------

    async def persist_to_redis(self) -> None:
        now = time.time()
        if now - self._last_persist < _PERSIST_INTERVAL_S:
            return
        self._last_persist = now
        try:
            from src.infrastructure.cache.redis_cache import get_cache

            cache = get_cache()
            data = json.dumps(
                {
                    "total": self._total_requests,
                    "failed": self._failed_requests,
                    "status_counts": self._status_counts,
                    "ts": now,
                }
            )
            await cache.set(_REDIS_KEY, data, ttl=_WINDOW_SECONDS)
        except Exception:
            logger.debug("SLO metric persist to Redis skipped (unavailable)")

    async def restore_from_redis(self) -> None:
        try:
            from src.infrastructure.cache.redis_cache import get_cache

            cache = get_cache()
            raw = await cache.get(_REDIS_KEY)
            if raw is None:
                return
            data = json.loads(raw) if isinstance(raw, str) else raw
            with self._lock:
                self._total_requests = max(self._total_requests, data.get("total", 0))
                self._failed_requests = max(self._failed_requests, data.get("failed", 0))
                for code_str, cnt in data.get("status_counts", {}).items():
                    code = int(code_str)
                    self._status_counts[code] = max(self._status_counts.get(code, 0), cnt)
            logger.info("SLO metrics restored from Redis")
        except Exception:
            logger.debug("SLO metric restore from Redis skipped")


class _HealthCheckTracker:
    """Tracks health-check probe outcomes (separate from API traffic)."""

    def __init__(self, max_samples: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._checks: deque[tuple[float, bool]] = deque(maxlen=max_samples)

    def record(self, *, healthy: bool) -> None:
        with self._lock:
            self._checks.append((time.time(), healthy))

    def availability(self, window_seconds: int = _WINDOW_SECONDS) -> dict[str, Any]:
        cutoff = time.time() - window_seconds
        with self._lock:
            while self._checks and self._checks[0][0] < cutoff:
                self._checks.popleft()
            total = len(self._checks)
            healthy_count = sum(1 for _, h in self._checks if h)

        pct = (healthy_count / total * 100) if total > 0 else 100.0
        return {
            "total_checks": total,
            "healthy_checks": healthy_count,
            "unhealthy_checks": total - healthy_count,
            "availability_pct": round(pct, 4),
        }


metrics_collector = _MetricsCollector()
health_tracker = _HealthCheckTracker()


class SLOMetricsMiddleware(BaseHTTPMiddleware):
    """Records per-request latency and status code for SLO calculation."""

    SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start

        # Record health-check outcomes separately
        if path in ("/healthz", "/readyz"):
            health_tracker.record(healthy=response.status_code < 500)
        else:
            metrics_collector.record(elapsed, status_code=response.status_code)

        # Best-effort periodic Redis flush (fire-and-forget)
        asyncio.ensure_future(metrics_collector.persist_to_redis())
        return response


# ------------------------------------------------------------------
# API endpoints
# ------------------------------------------------------------------


@router.get("/slo/current")
async def get_slo_metrics():
    """Get current SLO compliance metrics computed from live request data."""
    snap = metrics_collector.snapshot()
    hc = health_tracker.availability()
    return {
        "slos": [
            {
                "name": "API Availability",
                "target": 99.9,
                "current": snap["availability_pct"],
                "window": "30d",
                "budget_remaining_pct": snap["budget_remaining_pct"],
                "total_requests": snap["total_requests"],
                "failed_requests": snap["failed_requests"],
            },
            {
                "name": "API Latency P99",
                "target_ms": 500,
                "current_ms": snap["latency_p99_ms"],
                "p95_ms": snap["latency_p95_ms"],
                "p50_ms": snap["latency_p50_ms"],
                "window": "30d",
                "within_budget": snap["latency_p99_ms"] <= 500,
            },
            {
                "name": "Error Rate",
                "target_pct": 0.1,
                "current_pct": snap["error_rate_pct"],
                "window": "30d",
                "within_budget": snap["error_rate_pct"] <= 0.1,
                "status_code_counts": snap["status_code_counts"],
            },
            {
                "name": "Health Check Availability",
                "target": 99.95,
                "current": hc["availability_pct"],
                "window": "30d",
                "total_checks": hc["total_checks"],
                "unhealthy_checks": hc["unhealthy_checks"],
            },
        ],
    }


@router.get("/slo/metrics")
async def get_slo_raw_metrics():
    """Expose raw SLO metrics snapshot (availability, latency percentiles)."""
    return {
        "request_metrics": metrics_collector.snapshot(),
        "health_check_metrics": health_tracker.availability(),
    }
