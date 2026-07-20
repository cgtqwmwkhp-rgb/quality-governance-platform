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


broker_url: str
result_backend: str

_strict_celery = settings.is_production or (settings.is_staging and settings.external_audit_import_enabled)

if settings.celery_broker_url:
    broker_url = _normalize_redis_ssl_url(settings.celery_broker_url)
elif _strict_celery:
    raise ValueError(
        "CONFIGURATION ERROR: CELERY_BROKER_URL must be set in production "
        "(and in staging when external audit import is enabled). "
        "Silent localhost defaults are not allowed."
    )
else:
    broker_url = "redis://localhost:6379/0"
    logger.warning("CELERY_BROKER_URL not configured — using default redis://localhost:6379/0")

if settings.celery_result_backend:
    result_backend = _normalize_redis_ssl_url(settings.celery_result_backend)
elif settings.celery_broker_url:
    # Derive a distinct DB index from the broker when only broker is set.
    result_backend = _normalize_redis_ssl_url(settings.celery_broker_url)
elif _strict_celery:
    raise ValueError(
        "CONFIGURATION ERROR: CELERY_RESULT_BACKEND (or CELERY_BROKER_URL) must be set "
        "in production (and in staging when external audit import is enabled)."
    )
else:
    result_backend = "redis://localhost:6379/1"

if _strict_celery:
    lowered_broker = broker_url.lower()
    if "localhost" in lowered_broker or "127.0.0.1" in lowered_broker or "[::1]" in lowered_broker:
        raise ValueError(
            "CONFIGURATION ERROR: CELERY_BROKER_URL must not use localhost or 127.0.0.1 "
            "in production/staging with imports enabled."
        )

# Explicit task modules for worker import. Do NOT use
# autodiscover_tasks(["src.infrastructure.tasks"]) — that looks for a nested
# Django-style ``tasks.tasks`` module and silently skips these siblings, leaving
# the worker registry empty (inspect ping still works; send_email → NotRegistered).
CELERY_TASK_MODULES = (
    "src.infrastructure.tasks.cleanup_tasks",
    "src.infrastructure.tasks.competency_tasks",
    "src.infrastructure.tasks.dlq_replay",
    "src.infrastructure.tasks.document_campaign_tasks",
    "src.infrastructure.tasks.document_index_tasks",
    "src.infrastructure.tasks.email_tasks",
    "src.infrastructure.tasks.external_audit_import_tasks",
    "src.infrastructure.tasks.monitor_tasks",
    "src.infrastructure.tasks.notification_tasks",
    "src.infrastructure.tasks.pams_sync_tasks",
    "src.infrastructure.tasks.report_tasks",
    "src.infrastructure.tasks.safety_asset_expiry_tasks",
    "src.infrastructure.tasks.sms_tasks",
    "src.infrastructure.tasks.webhook_tasks",
    "src.infrastructure.tasks.regulatory_watch_tasks",
    "src.infrastructure.tasks.library_review_tasks",
    "src.infrastructure.tasks.training_matrix_upload_reminder_tasks",
)

celery_app = Celery(
    "quality_governance",
    broker=broker_url,
    backend=result_backend,
    include=list(CELERY_TASK_MODULES),
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
    imports=list(CELERY_TASK_MODULES),
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
    "check-safety-asset-expiry": {
        "task": "src.infrastructure.tasks.safety_asset_expiry_tasks.check_safety_asset_expiry",
        "schedule": crontab(hour=7, minute=30),  # Daily at 07:30 UTC
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
    "sync-pams-technicians": {
        "task": "src.infrastructure.tasks.pams_sync_tasks.sync_pams_technicians",
        "schedule": crontab(minute=0),  # Every hour
    },
    "recover-stale-import-jobs": {
        "task": "src.infrastructure.tasks.external_audit_import_tasks.recover_stale_import_jobs",
        "schedule": crontab(minute="*/10"),
    },
    "run-regulatory-watch": {
        "task": "src.infrastructure.tasks.regulatory_watch_tasks.run_regulatory_watch",
        "schedule": crontab(hour=5, minute=30, day_of_week="1"),  # Weekly Monday 05:30 UTC
    },
    "process-campaign-reminders": {
        "task": "src.infrastructure.tasks.document_campaign_tasks.process_campaign_reminders",
        "schedule": crontab(minute=15),  # Every hour at :15
    },
    "check-library-review-reminders": {
        "task": "src.infrastructure.tasks.library_review_tasks.check_library_review_reminders",
        "schedule": crontab(hour=7, minute=45),  # Daily at 07:45 UTC
    },
    "run-library-horizon-scan-daily": {
        "task": "src.infrastructure.tasks.library_review_tasks.run_library_horizon_scan",
        "schedule": crontab(hour=8, minute=0),  # Daily sweep of open packs (stub provider)
    },
    "remind-training-matrix-upload": {
        "task": ("src.infrastructure.tasks.training_matrix_upload_reminder_tasks." "remind_training_matrix_upload"),
        "schedule": crontab(hour=8, minute=0, day_of_week="fri"),  # Friday 08:00 UTC
    },
}

# DLQ signal handlers (not a @task module — keep explicit).
import src.infrastructure.tasks.dlq  # noqa: F401, E402
