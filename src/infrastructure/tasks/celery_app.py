"""Celery application configuration."""

import logging
import ssl
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from celery import Celery  # type: ignore[import-untyped]  # TYPE-IGNORE: MYPY-OVERRIDE
from celery.schedules import crontab  # type: ignore[import-untyped]  # TYPE-IGNORE: MYPY-OVERRIDE

from src.core.config import settings

logger = logging.getLogger(__name__)


def _normalize_redis_ssl_url(url: str) -> str:
    """Ensure Azure Redis `rediss://` URLs include the SSL requirement Kombu expects."""
    if urlsplit(url).scheme.lower() != "rediss":
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "ssl_cert_reqs" in query:
        return url

    query["ssl_cert_reqs"] = "CERT_REQUIRED"
    return urlunsplit(parts._replace(query=urlencode(query)))


def _redis_ssl_options(url: str) -> dict[str, Any] | None:
    """Provide explicit SSL settings because Celery strips URL query params from backend config."""
    if urlsplit(url).scheme.lower() != "rediss":
        return None
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED}


broker_url = (
    _normalize_redis_ssl_url(settings.celery_broker_url) if settings.celery_broker_url else "redis://localhost:6379/0"
)
result_backend = (
    _normalize_redis_ssl_url(settings.celery_result_backend)
    if settings.celery_result_backend
    else "redis://localhost:6379/1"
)

if not settings.celery_broker_url:
    logger.warning("CELERY_BROKER_URL not configured — using default redis://localhost:6379/0")

celery_app = Celery(
    "quality_governance",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "email": {"exchange": "email", "routing_key": "email"},
        "notifications": {"exchange": "notifications", "routing_key": "notifications"},
        "reports": {"exchange": "reports", "routing_key": "reports"},
        "cleanup": {"exchange": "cleanup", "routing_key": "cleanup"},
    },
    task_autoretry_for=(ConnectionError, TimeoutError, IOError),
    task_retry_backoff=True,
    task_retry_backoff_max=600,
    task_max_retries=3,
    task_retry_jitter=True,
    broker_use_ssl=_redis_ssl_options(broker_url),
    redis_backend_use_ssl=_redis_ssl_options(result_backend),
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens": {
        "task": "src.infrastructure.tasks.cleanup_tasks.cleanup_expired_tokens",
        "schedule": crontab(minute=0),  # Every hour
    },
    "run-data-retention": {
        "task": "src.infrastructure.tasks.cleanup_tasks.run_data_retention",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "check-expired-signatures": {
        "task": "src.infrastructure.tasks.cleanup_tasks.check_expired_signatures",
        "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
    },
    "check-competency-expiry": {
        "task": "src.infrastructure.tasks.competency_tasks.check_competency_expiry",
        "schedule": crontab(hour=7, minute=0),
    },
    "recalculate-compliance-scores": {
        "task": "src.infrastructure.tasks.report_tasks.recalculate_compliance_scores",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    "log-task-queue-depth": {
        "task": "src.infrastructure.tasks.monitor_tasks.log_task_queue_depth",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "replay-dlq-entries": {
        "task": "src.infrastructure.tasks.dlq_replay.replay_failed_tasks",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    "sync-pams-checklists": {
        "task": "src.infrastructure.tasks.pams_sync_tasks.sync_pams_checklists",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "recover-stale-import-jobs": {
        "task": "src.infrastructure.tasks.external_audit_import_tasks.recover_stale_import_jobs",
        "schedule": crontab(minute="*/10"),
    },
}

celery_app.autodiscover_tasks(
    [
        "src.infrastructure.tasks",
    ]
)

import src.infrastructure.tasks.dlq  # noqa: F401, E402
