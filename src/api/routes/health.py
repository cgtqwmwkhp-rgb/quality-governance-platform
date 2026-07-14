"""Health and resource monitoring endpoints."""

import asyncio
import logging
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict

import psutil
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.infrastructure.database import engine

_start_time = time.monotonic()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _probe_dlq_depth() -> dict[str, Any]:
    """Return pending FailedTask count for /readyz (informational)."""
    try:
        from sqlalchemy import func, select

        from src.domain.models.failed_task import FailedTask

        async with engine.connect() as conn:
            result = await asyncio.wait_for(
                conn.execute(select(func.count(FailedTask.id)).where(FailedTask.retried.is_(False))),
                timeout=2.0,
            )
            return {
                "status": "ok",
                "depth": int(result.scalar() or 0),
                "warn_threshold": 10,
                "critical_threshold": 50,
            }
    except Exception as exc:
        logger.warning("Readiness probe: DLQ depth check failed: %s", exc)
        return {
            "status": "error",
            "depth": None,
            "warn_threshold": 10,
            "critical_threshold": 50,
        }


def _lane1_channel_snapshot() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load push/email/SMS readiness (Lane-1 honesty helpers)."""
    from src.infrastructure.email.email_status import get_email_readiness
    from src.infrastructure.push.vapid_status import get_vapid_readiness
    from src.infrastructure.sms.sms_status import get_sms_readiness

    return get_vapid_readiness(), get_email_readiness(), get_sms_readiness()


def _attach_channel_notes(
    target: dict[str, Any],
    *,
    vapid: dict[str, Any],
    email: dict[str, Any],
    sms: dict[str, Any],
) -> None:
    if vapid.get("note"):
        target["push_note"] = vapid["note"]
    if email.get("note"):
        target["email_note"] = email["note"]
    if sms.get("note"):
        target["sms_note"] = sms["note"]


def _build_api_readyz_checks(
    *,
    db_status: str,
    db_latency_ms: float | None,
    redis_status: str,
    pams_status: str,
    pams_tables_reflected: int,
    vapid: dict[str, Any],
    email: dict[str, Any],
    sms: dict[str, Any],
    dlq: dict[str, Any],
    circuit_breakers: dict[str, Any],
    redis_required: bool,
    upstream_ai: dict[str, Any] | None = None,
    upstream_storage: dict[str, Any] | None = None,
    upstream_celery: dict[str, Any] | None = None,
    upstream_degraded: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "database": db_status,
        "database_latency_ms": db_latency_ms,
        "redis": redis_status,
        "pams": pams_status,
        "pams_tables_reflected": pams_tables_reflected,
        "push": vapid["status"],
        "vapid": {
            "status": vapid["status"],
            "public_key_present": vapid["public_key_present"],
            "private_key_present": vapid["private_key_present"],
            "contact_email_configured": vapid["contact_email_configured"],
            "library": vapid["library"],
        },
        "email_configured": email["email_configured"],
        "email": {
            "status": email["status"],
            "email_enabled": email["email_enabled"],
            "email_configured": email["email_configured"],
            "smtp_user_present": email["smtp_user_present"],
            "smtp_password_present": email["smtp_password_present"],
            "from_email_present": email["from_email_present"],
        },
        "sms_configured": sms["sms_configured"],
        "sms": {
            "status": sms["status"],
            "sms_enabled": sms["sms_enabled"],
            "sms_configured": sms["sms_configured"],
            "twilio_account_sid_present": sms["twilio_account_sid_present"],
            "twilio_auth_token_present": sms["twilio_auth_token_present"],
            "twilio_from_number_present": sms["twilio_from_number_present"],
            "library": sms["library"],
        },
        "dlq": dlq,
        "channels": {
            "email": email["status"],
            "sms": sms["status"],
            "push": vapid["status"],
        },
        "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "circuit_breakers": circuit_breakers,
        "upstream": {
            "ai": upstream_ai or {"status": "unknown"},
            "storage": upstream_storage or {"status": "unknown"},
            "celery": upstream_celery or {"status": "unknown"},
            "degraded": upstream_degraded
            or {
                "status": "unknown",
                "degraded": False,
                "open_circuits": [],
                "half_open_circuits": [],
                "affects_readiness": False,
            },
        },
    }
    _attach_channel_notes(checks, vapid=vapid, email=email, sms=sms)
    if upstream_ai and upstream_ai.get("note"):
        checks["upstream_ai_note"] = upstream_ai["note"]
    if upstream_storage and upstream_storage.get("note"):
        checks["upstream_storage_note"] = upstream_storage["note"]
    if upstream_celery and upstream_celery.get("note"):
        checks["upstream_celery_note"] = upstream_celery["note"]
    if upstream_degraded and upstream_degraded.get("note"):
        checks["upstream_degraded_note"] = upstream_degraded["note"]
    if redis_status == "not_configured":
        if redis_required:
            checks["redis_note"] = (
                "REDIS_URL is required in this environment for rate limiting, "
                "idempotency, and/or external audit imports."
            )
        else:
            checks["redis_note"] = (
                "Redis is optional for readiness; set REDIS_URL when using distributed cache or rate limits."
            )
    return checks


def _basic_health_payload() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": os.getenv("APP_VERSION", "dev"),
    }


@router.get("", response_model=Dict[str, Any], include_in_schema=True)
@router.get("/", response_model=Dict[str, Any], include_in_schema=False)
async def health_root():
    """Alias for probes that hit ``/api/v1/health`` (without ``/healthz``)."""
    return _basic_health_payload()


@router.get("/healthz", response_model=Dict[str, Any])
async def health_check():
    """Basic health check."""
    return _basic_health_payload()


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

    from src.core.config import settings

    try:
        import redis.asyncio as aioredis

        if settings.redis_url:
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await asyncio.wait_for(r.ping(), timeout=2.0)
            await r.aclose()
        else:
            redis_status = "not_configured"
            if settings.is_redis_required:
                overall_status = "not_ready"
                status_code = 503
    except Exception as exc:
        logger.warning("Readiness probe: Redis check failed: %s", exc)
        redis_status = "degraded"
        if settings.is_redis_required:
            overall_status = "not_ready"
            status_code = 503

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

    # WCS-B06 / Lane-1 channels: push/SMTP/SMS informational (PagerDuty removed — EA-05 Cancelled)
    vapid, email, sms = _lane1_channel_snapshot()
    from src.infrastructure.upstream.ai_status import get_upstream_ai_readiness
    from src.infrastructure.upstream.celery_status import get_upstream_celery_readiness
    from src.infrastructure.upstream.degraded_status import get_upstream_degraded_readiness
    from src.infrastructure.upstream.storage_status import get_upstream_storage_readiness

    upstream_ai = get_upstream_ai_readiness()
    upstream_storage = get_upstream_storage_readiness()
    upstream_celery = await get_upstream_celery_readiness()
    # Informational only — never flips readiness HTTP status.
    upstream_degraded = get_upstream_degraded_readiness()

    dlq = await _probe_dlq_depth()
    checks = _build_api_readyz_checks(
        db_status=db_status,
        db_latency_ms=db_latency_ms,
        redis_status=redis_status,
        pams_status=pams_status,
        pams_tables_reflected=pams_tables_reflected,
        vapid=vapid,
        email=email,
        sms=sms,
        dlq=dlq,
        circuit_breakers=circuit_breakers,
        redis_required=settings.is_redis_required,
        upstream_ai=upstream_ai,
        upstream_storage=upstream_storage,
        upstream_celery=upstream_celery,
        upstream_degraded=upstream_degraded,
    )

    payload = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }

    return JSONResponse(content=payload, status_code=status_code)


@router.get("/diagnostics", response_model=Dict[str, Any])
async def diagnostics():
    """Runtime diagnostics for operational visibility. No DB queries."""
    migration_head = "unknown"
    try:
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            migration_head = result.stdout.strip().split("\n")[-1]
    except Exception:
        migration_head = "unavailable"

    feature_flag_count = 0
    try:
        from src.core.config import settings

        feature_flag_count = len([k for k in dir(settings) if k.startswith("feature_") or k.startswith("ff_")])
    except Exception:
        pass

    # Registry freshness check (D32 supportability — AP-12)
    registry_status: dict[str, Any] = {}
    try:
        import json as _json
        from pathlib import Path as _Path

        report_path = _Path("docs/evidence/registry-validation-report.json")
        if report_path.exists():
            report = _json.loads(report_path.read_text())
            registry_status = {
                "last_validated": report.get("generated_at", "unknown"),
                "registries_checked": report.get("registries_checked", 0),
                "passed": report.get("passed", False),
                "warnings": report.get("warnings", []),
                "errors": report.get("errors", []),
            }
        else:
            registry_status = {"status": "report_not_found", "path": str(report_path)}
    except Exception as _exc:
        registry_status = {"status": "error", "detail": str(_exc)}

    # Migration reversibility evidence (D12/D32 — AP-C)
    migration_reversibility: dict[str, Any] = {}
    try:
        import json as _json2
        from pathlib import Path as _Path2

        rev_path = _Path2("docs/evidence/migration-reversibility-evidence.json")
        if rev_path.exists():
            rev_data = _json2.loads(rev_path.read_text())
            migration_reversibility = {
                "last_checked": rev_data.get("generated_at", "unknown"),
                "total_migrations": rev_data.get("total_migrations", "?"),
                "reversibility_check": rev_data.get("reversibility_check", "unknown"),
                "ci_run_id": rev_data.get("ci_run_id", "unknown"),
                "head_sha": rev_data.get("head_sha", "unknown"),
            }
        else:
            migration_reversibility = {"status": "evidence_pending", "note": "First CI run will generate this"}
    except Exception as _exc2:
        migration_reversibility = {"status": "error", "detail": str(_exc2)}

    # Build SHA (D32 — deployment identity)
    build_sha = os.getenv("BUILD_SHA", os.getenv("GITHUB_SHA", "dev"))[:12]

    # Idempotency middleware key-scoping info (D24 — operational transparency)
    idempotency_info = {
        "scoping": "tenant_fingerprint + method + path + client_key",
        "ttl_seconds": 86400,
        "redis_configured": bool(os.getenv("REDIS_URL")),
    }

    return {
        "app_version": os.getenv("APP_VERSION", "dev"),
        "build_sha": build_sha,
        "python_version": platform.python_version(),
        "migration_head": migration_head,
        "migration_reversibility": migration_reversibility,
        "telemetry_enabled": os.getenv("TELEMETRY_ENABLED", "true"),
        "feature_flag_count": feature_flag_count,
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "registry_freshness": registry_status,
        "idempotency": idempotency_info,
        "runbooks": {
            "deployment": "docs/DEPLOYMENT_RUNBOOK.md",
            "disaster_recovery": "docs/ops/DISASTER_RECOVERY_RUNBOOK.md",
            "rollback": "docs/runbooks/rollback-drills.md",
            "support_escalation": "docs/runbooks/support-escalation.md",
            "kql_queries": "docs/ops/kql-queries.md",
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
