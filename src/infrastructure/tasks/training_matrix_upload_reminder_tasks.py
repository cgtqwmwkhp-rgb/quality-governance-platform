"""Friday in-app reminder to upload the weekly Atlas training matrix CSV.

Creates a standard notification for active admin users (per tenant), deep-linking
to Training → Admin. Deduped once per ISO week so Celery retries / re-runs do
not spam the bell.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, TypedDict

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ENTITY_TYPE = "training_matrix_upload"
NOTIFICATION_CATEGORY = "training_matrix_friday_upload"
DEFAULT_ADMIN_ROLE = "admin"
ADMIN_ROLE_ENV = "TRAINING_MATRIX_UPLOAD_ADMIN_ROLE"
ACTION_URL = "/workforce/training?tab=admin"


class _ReminderResults(TypedDict):
    admins_considered: int
    notifications_created: int
    notifications_skipped_dedupe: int
    admin_role: str
    week_key: str


def _admin_role_name() -> str:
    return (os.getenv(ADMIN_ROLE_ENV) or DEFAULT_ADMIN_ROLE).strip() or DEFAULT_ADMIN_ROLE


def week_key(now: Optional[datetime] = None) -> str:
    """ISO year-week used for Friday reminder dedupe (e.g. 2026-W29)."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def dedupe_key_for_week(week: str) -> str:
    return f"{ENTITY_TYPE}:{week}"


def notification_exists_for_week(
    existing_rows: Iterable[Any],
    *,
    user_id: int,
    week: str,
) -> bool:
    key = dedupe_key_for_week(week)
    for row in existing_rows:
        if getattr(row, "user_id", None) != user_id:
            continue
        if getattr(row, "entity_type", None) != ENTITY_TYPE:
            continue
        if str(getattr(row, "entity_id", "")) != week:
            continue
        extra = getattr(row, "extra_data", None) or {}
        if extra.get("dedupe_key") == key or extra.get("week_key") == week:
            return True
    return False


def build_notification_kwargs(
    *,
    user_id: int,
    week: str,
    tenant_id: Optional[int] = None,
    last_upload_label: Optional[str] = None,
) -> dict[str, Any]:
    from src.domain.models.notification import NotificationPriority, NotificationType

    last_line = (
        f" Last upload on file: {last_upload_label}."
        if last_upload_label
        else " No Atlas matrix has been uploaded yet."
    )
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "type": NotificationType.SYSTEM_ANNOUNCEMENT,
        "priority": NotificationPriority.MEDIUM,
        "title": "Upload this week's Atlas training matrix",
        "message": (
            "Friday reminder: export the Atlas Training Matrix Report as CSV and upload it "
            f"under Training → Admin. The new file replaces last week's completion data.{last_line}"
        ),
        "entity_type": ENTITY_TYPE,
        "entity_id": week,
        "action_url": ACTION_URL,
        "extra_data": {
            "notification_category": NOTIFICATION_CATEGORY,
            "week_key": week,
            "dedupe_key": dedupe_key_for_week(week),
        },
        "delivered_channels": ["in_app"],
    }


def format_last_upload_label(
    *,
    created_at: Optional[datetime],
    uploaded_by_name: Optional[str],
    filename: Optional[str],
) -> Optional[str]:
    if created_at is None and not filename:
        return None
    when = created_at.astimezone(timezone.utc).strftime("%d %b %Y %H:%M UTC") if created_at else "unknown time"
    who = uploaded_by_name or "unknown user"
    name = filename or "matrix.csv"
    return f"{when} by {who} ({name})"


@celery_app.task(
    name="src.infrastructure.tasks.training_matrix_upload_reminder_tasks.remind_training_matrix_upload",
    queue="notifications",
    bind=True,
    max_retries=3,
)
def remind_training_matrix_upload(self) -> _ReminderResults:
    """Emit Friday Atlas upload reminders to active admin users."""
    from sqlalchemy import select

    from src.domain.models.notification import Notification
    from src.domain.models.training_matrix import TrainingMatrixImport
    from src.domain.models.user import Role, User
    from src.infrastructure.database import SessionLocal

    now = datetime.now(timezone.utc)
    week = week_key(now)
    results: _ReminderResults = {
        "admins_considered": 0,
        "notifications_created": 0,
        "notifications_skipped_dedupe": 0,
        "admin_role": _admin_role_name(),
        "week_key": week,
    }

    try:
        with SessionLocal() as db:
            admin_role = _admin_role_name()
            admin_rows = (
                db.execute(
                    select(User)
                    .join(User.roles)
                    .where(
                        Role.name == admin_role,
                        User.is_active.is_(True),
                    )
                )
                .scalars()
                .all()
            )
            results["admins_considered"] = len(admin_rows)

            # Latest import per tenant for message context.
            latest_by_tenant: dict[Optional[int], TrainingMatrixImport] = {}
            for imp in (
                db.execute(select(TrainingMatrixImport).order_by(TrainingMatrixImport.id.desc())).scalars().all()
            ):
                if imp.tenant_id not in latest_by_tenant:
                    latest_by_tenant[imp.tenant_id] = imp

            uploader_ids = {imp.uploaded_by_user_id for imp in latest_by_tenant.values() if imp.uploaded_by_user_id}
            uploader_names: dict[int, str] = {}
            if uploader_ids:
                for user in db.execute(select(User).where(User.id.in_(uploader_ids))).scalars().all():
                    uploader_names[user.id] = user.full_name

            for admin in admin_rows:
                existing = (
                    db.execute(
                        select(Notification).where(
                            Notification.user_id == admin.id,
                            Notification.entity_type == ENTITY_TYPE,
                            Notification.entity_id == week,
                        )
                    )
                    .scalars()
                    .all()
                )
                if notification_exists_for_week(existing, user_id=admin.id, week=week):
                    results["notifications_skipped_dedupe"] += 1
                    continue

                latest = latest_by_tenant.get(admin.tenant_id)
                last_label = None
                if latest:
                    last_label = format_last_upload_label(
                        created_at=getattr(latest, "created_at", None),
                        uploaded_by_name=uploader_names.get(latest.uploaded_by_user_id or 0),
                        filename=latest.filename,
                    )

                kwargs = build_notification_kwargs(
                    user_id=admin.id,
                    week=week,
                    tenant_id=admin.tenant_id,
                    last_upload_label=last_label,
                )
                db.add(Notification(**kwargs))
                results["notifications_created"] += 1

            db.commit()

        logger.info("Training matrix Friday upload reminder completed: %s", results)
    except Exception as exc:
        logger.error("Training matrix Friday upload reminder failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)

    return results
