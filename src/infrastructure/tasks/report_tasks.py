"""Long-running report generation tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.report_tasks.generate_compliance_report",
    bind=True,
    max_retries=1,
    queue="reports",
    soft_time_limit=600,
)
def generate_compliance_report(
    self, tenant_id: int, standard: str, format: str = "pdf"
) -> dict:
    """Generate a compliance report for a tenant."""
    try:
        logger.info(
            "Generating %s compliance report for tenant %d", standard, tenant_id
        )
        return {
            "status": "completed",
            "tenant_id": tenant_id,
            "standard": standard,
            "format": format,
        }
    except Exception as exc:
        logger.error("Report generation failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="src.infrastructure.tasks.report_tasks.recalculate_compliance_scores",
    queue="reports",
)
def recalculate_compliance_scores() -> dict:
    """Recalculate compliance scores for all tenants. Runs daily via beat."""
    logger.info("Recalculating compliance scores")
    return {"status": "completed"}
