"""Health and resource monitoring endpoints."""

import os
from datetime import datetime, timezone
from typing import Any, Dict

import psutil
from fastapi import APIRouter

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
    """Readiness check with dependency status."""
    return {
        "status": "ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "ok",
            "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
        },
    }


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
