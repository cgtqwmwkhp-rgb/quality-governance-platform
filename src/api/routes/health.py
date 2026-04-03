"""Health and resource monitoring endpoints."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import psutil
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.infrastructure.database import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=Dict[str, Any])
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": os.getenv("APP_VERSION", "dev"),
    }


@router.get("/readyz", response_model=Dict[str, Any])
async def readiness_check():
    """Readiness check with real dependency verification (DB + Redis)."""
    db_status = "ok"
    db_latency_ms: float | None = None
    redis_status = "ok"
    overall_status = "ready"
    status_code = 200

    try:
        start = asyncio.get_event_loop().time()
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=3.0)
        db_latency_ms = round((asyncio.get_event_loop().time() - start) * 1000, 1)
    except Exception as exc:
        logger.warning("Readiness probe: database check failed: %s", exc)
        db_status = "degraded"
        overall_status = "not_ready"
        status_code = 503

    try:
        import redis.asyncio as aioredis

        from src.core.config import settings

        if settings.redis_url:
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await asyncio.wait_for(r.ping(), timeout=2.0)
            await r.aclose()
        else:
            redis_status = "not_configured"
    except Exception as exc:
        logger.warning("Readiness probe: Redis check failed: %s", exc)
        redis_status = "degraded"

    pams_status = "not_configured"
    pams_tables_reflected = 0
    try:
        from src.infrastructure.pams_database import _pams_tables, is_pams_available

        if is_pams_available():
            pams_tables_reflected = len(_pams_tables)
            pams_status = "ok" if pams_tables_reflected > 0 else "no_tables"
    except Exception as exc:
        logger.warning("Readiness probe: PAMS check failed: %s", exc)
        pams_status = "error"

    circuit_breakers = {}
    try:
        from src.infrastructure.resilience.circuit_breaker import get_all_circuits

        for cb in get_all_circuits():
            circuit_breakers[cb.name] = cb.get_health()
    except Exception:
        pass

    payload = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_status,
            "database_latency_ms": db_latency_ms,
            "redis": redis_status,
            "pams": pams_status,
            "pams_tables_reflected": pams_tables_reflected,
            "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "circuit_breakers": circuit_breakers,
        },
    }

    return JSONResponse(content=payload, status_code=status_code)


@router.get("/metrics/resources", response_model=Dict[str, Any])
async def resource_metrics():
    """Resource utilization metrics for cost monitoring."""
    process = psutil.Process()
    mem = process.memory_info()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "process": {
            "memory_rss_mb": round(mem.rss / 1024 / 1024, 1),
            "memory_vms_mb": round(mem.vms / 1024 / 1024, 1),
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads(),
            "open_files": len(process.open_files()),
        },
        "system": {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_total_mb": round(psutil.virtual_memory().total / 1024 / 1024, 1),
            "memory_used_percent": psutil.virtual_memory().percent,
            "disk_used_percent": psutil.disk_usage("/").percent,
        },
    }


@router.get("/diagnostics", response_model=Dict[str, Any])
async def diagnostics():
    """Aggregated diagnostic snapshot for operational triage."""
    import hashlib

    from src.core.config import settings

    config_keys = sorted(k for k in dir(settings) if not k.startswith("_") and k.isupper())
    config_hash = hashlib.sha256("|".join(f"{k}={getattr(settings, k, '')}" for k in config_keys).encode()).hexdigest()[
        :16
    ]

    db_ok = True
    pool_usage = None
    try:
        from src.infrastructure.database import get_pool_usage_percent

        pool_usage = get_pool_usage_percent()
    except Exception:
        pass
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    feature_flags = {}
    try:
        from src.domain.services.feature_flag_service import FeatureFlagService  # noqa: F401

        feature_flags = {"source": "database", "status": "available"}
    except Exception:
        feature_flags = {"source": "unavailable"}

    circuit_breakers = {}
    try:
        from src.infrastructure.resilience.circuit_breaker import get_all_circuits

        for cb in get_all_circuits():
            circuit_breakers[cb.name] = cb.get_health()
    except Exception:
        pass

    process = psutil.Process()
    mem = process.memory_info()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": os.getenv("APP_VERSION", "dev"),
        "config_hash": config_hash,
        "database": {"connected": db_ok, "pool_usage_pct": pool_usage},
        "memory_rss_mb": round(mem.rss / 1024 / 1024, 1),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "feature_flags": feature_flags,
        "circuit_breakers": circuit_breakers,
    }
