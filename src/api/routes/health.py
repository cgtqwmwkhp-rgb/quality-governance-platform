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

    payload = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_status,
            "database_latency_ms": db_latency_ms,
            "redis": redis_status,
            "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
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
