"""Redis/Celery upstream readiness helpers (Path-to-10 S10 honesty).

Reports broker/config presence and Redis list depths for known Celery queues.
Missing broker stays ``not_configured`` and does not fail the readiness probe.
Worker inspect ping is intentionally skipped here (CI smoke covers that path).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# Queues declared across task modules / celery_app.task_default_queue.
KNOWN_QUEUES: tuple[str, ...] = (
    "default",
    "email",
    "notifications",
    "reports",
    "cleanup",
)


def _present(raw: str | None) -> bool:
    return bool((raw or "").strip())


def _broker_scheme(url: str) -> str | None:
    if not url:
        return None
    try:
        return urlsplit(url).scheme.lower() or None
    except Exception:
        return None


def _config_snapshot() -> dict[str, Any]:
    broker = (os.getenv("CELERY_BROKER_URL") or "").strip()
    redis_url = (os.getenv("REDIS_URL") or "").strip()
    result_backend = (os.getenv("CELERY_RESULT_BACKEND") or "").strip()

    broker_present = _present(broker)
    redis_present = _present(redis_url)
    backend_present = _present(result_backend)

    if broker_present:
        status = "configured"
    elif redis_present:
        # Ops often point Celery at REDIS_URL when CELERY_BROKER_URL is unset.
        status = "partial"
    else:
        status = "not_configured"

    payload: dict[str, Any] = {
        "status": status,
        "role": "broker_queues",
        "broker_url_present": broker_present,
        "redis_url_present": redis_present,
        "result_backend_present": backend_present,
        "broker_scheme": _broker_scheme(broker) if broker_present else None,
        "queues_tracked": list(KNOWN_QUEUES),
        "workers_ping": "skipped",
        "workers_ping_note": (
            "Celery inspect.ping is not run on /readyz (keeps the probe fast). "
            "Use scripts/celery/smoke_inspect_ping.py in CI/deploy smoke."
        ),
    }

    if status == "not_configured":
        payload["note"] = (
            "Celery/Redis broker is not configured. Set CELERY_BROKER_URL "
            "(and optionally REDIS_URL / CELERY_RESULT_BACKEND) via Key Vault / "
            "App Settings when background workers are required."
        )
    elif status == "partial":
        payload["note"] = (
            "REDIS_URL is present but CELERY_BROKER_URL is unset. "
            "Queue depth may still be readable from Redis; set CELERY_BROKER_URL "
            "explicitly for production workers."
        )
    return payload


async def _probe_queue_depths(redis_url: str) -> dict[str, Any]:
    """LLEN known Celery queue keys. Informational only — never raises to caller."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url, socket_connect_timeout=2)
        try:
            depths: dict[str, int] = {}
            for queue in KNOWN_QUEUES:
                depths[queue] = int(await asyncio.wait_for(client.llen(queue), timeout=1.0))
            return {
                "depth_status": "ok",
                "queues": depths,
                "total_depth": int(sum(depths.values())),
            }
        finally:
            await client.aclose()
    except Exception as exc:
        logger.warning("Readiness probe: Celery queue depth check failed: %s", exc)
        return {
            "depth_status": "error",
            "queues": {},
            "total_depth": None,
            "depth_error": type(exc).__name__,
        }


async def get_upstream_celery_readiness() -> dict[str, Any]:
    """Return Celery/Redis broker config + optional queue depth without secrets."""
    payload = _config_snapshot()
    broker = (os.getenv("CELERY_BROKER_URL") or "").strip()
    redis_url = (os.getenv("REDIS_URL") or "").strip()
    probe_url = broker or redis_url

    if not probe_url:
        payload["depth_status"] = "not_configured"
        payload["queues"] = {}
        payload["total_depth"] = None
        return payload

    scheme = _broker_scheme(probe_url)
    if scheme not in {"redis", "rediss"}:
        payload["depth_status"] = "unsupported_scheme"
        payload["queues"] = {}
        payload["total_depth"] = None
        payload["depth_note"] = (
            f"Queue depth probe supports redis/rediss only (got {scheme!r}). "
            "Broker URL presence is still reported above."
        )
        return payload

    depth = await _probe_queue_depths(probe_url)
    payload.update(depth)
    return payload
