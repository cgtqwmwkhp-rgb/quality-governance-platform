"""Celery tasks for Safety Asset Management expiry notifications (AM-NOTIFY).

Daily beat sweep classifies assets into exclusive bands (due_30 / due_60 /
due_90 / overdue) from ``expiry_date`` and optionally ``next_service_due``,
then creates in-app notifications for the owner plus a configurable admin
role. Notifications deep-link to ``/safety-assets/:id`` and are deduped per
(user, asset, band).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ENTITY_TYPE = "safety_asset"
NOTIFICATION_CATEGORY = "safety_asset_expiry"
DEFAULT_ADMIN_ROLE = "admin"
ADMIN_ROLE_ENV = "SAFETY_ASSET_EXPIRY_ADMIN_ROLE"

# Exclusive upper bounds (days until due). Overdue is handled separately.
BAND_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("due_30", 0, 30),
    ("due_60", 31, 60),
    ("due_90", 61, 90),
)

def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def effective_due_date(
    expiry_date: Optional[datetime],
    next_service_due: Optional[datetime] = None,
    *,
    include_service_due: bool = True,
) -> Optional[datetime]:
    """Return the earliest relevant due datetime for band classification."""
    candidates: list[datetime] = []
    if expiry_date is not None:
        candidates.append(_as_utc(expiry_date))
    if include_service_due and next_service_due is not None:
        candidates.append(_as_utc(next_service_due))
    if not candidates:
        return None
    return min(candidates)


def classify_expiry_band(
    due_at: Optional[datetime],
    *,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Map a due datetime to an exclusive band, or None when outside windows.

    Bands:
    - overdue: due_at < now
    - due_30: 0..30 days inclusive
    - due_60: 31..60 days inclusive
    - due_90: 61..90 days inclusive
    """
    if due_at is None:
        return None

    current = _as_utc(now or datetime.now(timezone.utc))
    due = _as_utc(due_at)
    delta = due - current
    # Floor whole days so "expires in 30d 1h" still lands in due_30.
    days_until = int(delta.total_seconds() // 86400)

    if days_until < 0:
        return "overdue"

    for band, low, high in BAND_WINDOWS:
        if low <= days_until <= high:
            return band
    return None


def dedupe_key(asset_id: int, band: str) -> str:
    """Stable key used in notification extra_data for asset/band dedupe."""
    return f"{ENTITY_TYPE}:{asset_id}:{band}"


def action_url_for_asset(asset_id: int) -> str:
    return f"/safety-assets/{asset_id}"


def _admin_role_name() -> str:
    return (os.getenv(ADMIN_ROLE_ENV) or DEFAULT_ADMIN_ROLE).strip() or DEFAULT_ADMIN_ROLE


def _priority_for_band(band: str):
    from src.domain.models.notification import NotificationPriority

    if band == "overdue":
        return NotificationPriority.HIGH
    if band == "due_30":
        return NotificationPriority.HIGH
    if band == "due_60":
        return NotificationPriority.MEDIUM
    return NotificationPriority.LOW


def _notification_type_for_band(band: str):
    from src.domain.models.notification import NotificationType

    if band == "overdue":
        return NotificationType.CERTIFICATE_EXPIRED
    return NotificationType.CERTIFICATE_EXPIRING


def _title_for_band(band: str, asset_name: str) -> str:
    labels = {
        "overdue": "Safety asset overdue",
        "due_30": "Safety asset due within 30 days",
        "due_60": "Safety asset due within 60 days",
        "due_90": "Safety asset due within 90 days",
    }
    return f"{labels.get(band, 'Safety asset due')}: {asset_name}"


def _message_for_band(
    band: str,
    *,
    asset_number: str,
    asset_name: str,
    due_at: datetime,
) -> str:
    due_label = _as_utc(due_at).date().isoformat()
    if band == "overdue":
        return (
            f"Safety asset {asset_number} ({asset_name}) is overdue "
            f"(due {due_label}). Review and renew or quarantine as required."
        )
    window = {"due_30": "30", "due_60": "60", "due_90": "90"}.get(band, "?")
    return (
        f"Safety asset {asset_number} ({asset_name}) is due within {window} days "
        f"(due {due_label}). Open the asset register to take action."
    )


def notification_exists_for_band(
    existing_rows: Iterable[Any],
    *,
    user_id: int,
    asset_id: int,
    band: str,
) -> bool:
    """Return True when a notification for this user/asset/band already exists."""
    key = dedupe_key(asset_id, band)
    for row in existing_rows:
        if getattr(row, "user_id", None) != user_id:
            continue
        if getattr(row, "entity_type", None) != ENTITY_TYPE:
            continue
        if str(getattr(row, "entity_id", "")) != str(asset_id):
            continue
        extra = getattr(row, "extra_data", None) or {}
        if extra.get("band") == band or extra.get("dedupe_key") == key:
            return True
    return False


def recipient_user_ids(
    *,
    owner_user_id: Optional[int],
    admin_user_ids: Iterable[int],
) -> list[int]:
    """Owner + admins, de-duplicated, order-stable (owner first)."""
    seen: set[int] = set()
    ordered: list[int] = []
    for uid in ([owner_user_id] if owner_user_id else []) + list(admin_user_ids):
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)
    return ordered


def build_notification_kwargs(
    *,
    user_id: int,
    asset_id: int,
    asset_number: str,
    asset_name: str,
    band: str,
    due_at: datetime,
    tenant_id: Optional[int] = None,
) -> dict[str, Any]:
    """Pure helper: kwargs for constructing a Notification row."""
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "type": _notification_type_for_band(band),
        "priority": _priority_for_band(band),
        "title": _title_for_band(band, asset_name),
        "message": _message_for_band(
            band,
            asset_number=asset_number,
            asset_name=asset_name,
            due_at=due_at,
        ),
        "entity_type": ENTITY_TYPE,
        "entity_id": str(asset_id),
        "action_url": action_url_for_asset(asset_id),
        "extra_data": {
            "notification_category": NOTIFICATION_CATEGORY,
            "band": band,
            "dedupe_key": dedupe_key(asset_id, band),
            "due_at": _as_utc(due_at).isoformat(),
        },
        "delivered_channels": ["in_app"],
    }


@celery_app.task(
    name="src.infrastructure.tasks.safety_asset_expiry_tasks.check_safety_asset_expiry",
    queue="notifications",
    bind=True,
    max_retries=3,
)
def check_safety_asset_expiry(self) -> dict:
    """Sweep assets and emit in-app expiry-band notifications.

    Runs daily via Celery beat. Dedupes per (user, asset, band) so repeat runs
    do not spam. Admin recipients come from ``SAFETY_ASSET_EXPIRY_ADMIN_ROLE``
    (default: ``admin``).
    """
    from sqlalchemy import or_, select

    from src.domain.models.asset import Asset, AssetCategory, AssetStatus, AssetType
    from src.domain.models.notification import Notification
    from src.domain.models.user import Role, User
    from src.infrastructure.database import SessionLocal

    now = datetime.now(timezone.utc)
    results = {
        "assets_scanned": 0,
        "in_band": 0,
        "notifications_created": 0,
        "notifications_skipped_dedupe": 0,
        "admin_role": _admin_role_name(),
    }

    try:
        with SessionLocal() as db:
            assets = (
                db.execute(
                    select(Asset)
                    .join(AssetType, Asset.asset_type_id == AssetType.id)
                    .where(
                        AssetType.category == AssetCategory.SAFETY,
                        Asset.status != AssetStatus.DECOMMISSIONED,
                        or_(
                            Asset.expiry_date.is_not(None),
                            Asset.next_service_due.is_not(None),
                        ),
                    )
                )
                .scalars()
                .all()
            )
            results["assets_scanned"] = len(assets)

            admin_role = _admin_role_name()
            admin_rows = db.execute(
                select(User.id, User.tenant_id)
                .join(User.roles)
                .where(
                    Role.name == admin_role,
                    User.is_active.is_(True),
                )
            ).all()

            for asset in assets:
                due_at = effective_due_date(asset.expiry_date, asset.next_service_due)
                band = classify_expiry_band(due_at, now=now)
                if band is None or due_at is None:
                    continue
                results["in_band"] += 1

                admin_ids = [
                    admin_id
                    for admin_id, admin_tenant_id in admin_rows
                    if admin_tenant_id is None or admin_tenant_id == asset.tenant_id
                ]
                recipients = recipient_user_ids(
                    owner_user_id=asset.owner_user_id,
                    admin_user_ids=admin_ids,
                )
                if not recipients:
                    continue

                existing = (
                    db.execute(
                        select(Notification).where(
                            Notification.entity_type == ENTITY_TYPE,
                            Notification.entity_id == str(asset.id),
                            Notification.user_id.in_(recipients),
                        )
                    )
                    .scalars()
                    .all()
                )

                for user_id in recipients:
                    if notification_exists_for_band(
                        existing,
                        user_id=user_id,
                        asset_id=asset.id,
                        band=band,
                    ):
                        results["notifications_skipped_dedupe"] += 1
                        continue

                    kwargs = build_notification_kwargs(
                        user_id=user_id,
                        asset_id=asset.id,
                        asset_number=asset.asset_number,
                        asset_name=asset.name,
                        band=band,
                        due_at=due_at,
                        tenant_id=asset.tenant_id,
                    )
                    db.add(Notification(**kwargs))
                    results["notifications_created"] += 1

            db.commit()

        logger.info("Safety asset expiry check completed: %s", results)
    except Exception as exc:
        logger.error("Safety asset expiry check failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)

    return results
