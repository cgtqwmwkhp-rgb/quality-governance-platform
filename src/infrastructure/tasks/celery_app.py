"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.core.config import settings

broker_url = settings.celery_broker_url
result_backend = settings.celery_result_backend

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
}

celery_app.autodiscover_tasks(
    [
        "src.infrastructure.tasks",
    ]
)

import src.infrastructure.tasks.dlq  # noqa: F401, E402
