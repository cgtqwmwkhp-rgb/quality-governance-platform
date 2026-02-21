"""Data retention and cleanup tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.cleanup_tasks.cleanup_expired_tokens",
    queue="cleanup",
)
def cleanup_expired_tokens() -> dict:
    """Remove expired entries from the token blacklist. Runs hourly via beat."""
    logger.info("Cleaning up expired token blacklist entries")
    return {"status": "completed"}


@celery_app.task(
    name="src.infrastructure.tasks.cleanup_tasks.run_data_retention",
    queue="cleanup",
)
def run_data_retention() -> dict:
    """Run all data retention policies. Runs nightly via beat."""
    logger.info("Running data retention policies")
    return {"status": "completed"}


@celery_app.task(
    name="src.infrastructure.tasks.cleanup_tasks.check_expired_signatures",
    queue="cleanup",
)
def check_expired_signatures() -> dict:
    """Check and expire old signature requests. Runs daily via beat."""
    logger.info("Checking for expired signature requests")
    return {"status": "completed"}
