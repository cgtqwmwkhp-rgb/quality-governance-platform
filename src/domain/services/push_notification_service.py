"""Push notification domain service.

Extracts subscription management, notification sending, preference handling,
and the Web Push delivery logic from the push_notifications route module.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.utils.update import apply_updates
from src.core.config import settings

logger = logging.getLogger(__name__)


class PushNotificationServiceDomain:
    """Manages Web Push subscriptions, preferences, and notification delivery."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.vapid_private_key = settings.vapid_private_key or None
        self.vapid_public_key = settings.vapid_public_key or None
        self.vapid_claims = {"sub": f"mailto:{settings.vapid_email}"}

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        subscription_data: BaseModel,
        user_id: int | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Register or reactivate a push subscription.

        Returns:
            Dict with success flag, subscription_id and message.
        """
        from src.api.routes.push_notifications import PushSubscription

        data = subscription_data.model_dump()
        endpoint = data["endpoint"]
        keys = data.get("keys", {})

        result = await self.db.execute(
            select(PushSubscription).filter(PushSubscription.endpoint == endpoint)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        )
        existing = result.scalars().first()

        if existing:
            existing.user_id = user_id  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
            existing.is_active = True  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
            existing.last_used_at = datetime.utcnow()  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
            await self.db.commit()
            return {
                "success": True,
                "subscription_id": existing.id,
                "message": "Subscribed to push notifications",
            }

        subscription = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=keys.get("p256dh", ""),
            auth_key=keys.get("auth", ""),
            user_agent=user_agent,
            is_active=True,
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        return {
            "success": True,
            "subscription_id": subscription.id,
            "message": "Subscribed to push notifications",
        }

    async def unsubscribe(self, endpoint: str) -> bool:
        """Deactivate a push subscription.

        Raises:
            LookupError: If no subscription for the endpoint exists.
        """
        from src.api.routes.push_notifications import PushSubscription

        result = await self.db.execute(
            select(PushSubscription).filter(PushSubscription.endpoint == endpoint)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        )
        subscription = result.scalars().first()

        if not subscription:
            raise LookupError("Subscription not found")

        subscription.is_active = False  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
        await self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    async def get_preferences(self, user_id: int) -> dict[str, Any]:
        from src.api.routes.push_notifications import NotificationPreference

        pref_result = await self.db.execute(
            select(NotificationPreference).filter(
                NotificationPreference.user_id == user_id  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        prefs = pref_result.scalars().first()

        if not prefs:
            return {
                "push_enabled": True,
                "email_enabled": True,
                "sms_enabled": False,
                "incident_alerts": True,
                "action_reminders": True,
                "audit_notifications": True,
                "compliance_updates": True,
                "mentions": True,
                "digest_frequency": "immediate",
            }

        return {
            "push_enabled": prefs.push_enabled,
            "email_enabled": prefs.email_enabled,
            "sms_enabled": prefs.sms_enabled,
            "incident_alerts": prefs.incident_alerts,
            "action_reminders": prefs.action_reminders,
            "audit_notifications": prefs.audit_notifications,
            "compliance_updates": prefs.compliance_updates,
            "mentions": prefs.mentions,
            "digest_frequency": prefs.digest_frequency,
            "quiet_hours_start": prefs.quiet_hours_start,
            "quiet_hours_end": prefs.quiet_hours_end,
        }

    async def update_preferences(self, user_id: int, updates: BaseModel) -> dict[str, Any]:
        from src.api.routes.push_notifications import NotificationPreference

        pref_result = await self.db.execute(
            select(NotificationPreference).filter(
                NotificationPreference.user_id == user_id  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        prefs = pref_result.scalars().first()

        if not prefs:
            prefs = NotificationPreference(user_id=user_id)
            self.db.add(prefs)

        apply_updates(prefs, updates)
        await self.db.commit()

        return {"success": True, "message": "Preferences updated"}

    # ------------------------------------------------------------------
    # Send notifications
    # ------------------------------------------------------------------

    async def send_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        url: str | None = None,
        data: dict | None = None,
        notification_type: str = "general",
    ) -> list[dict[str, Any]]:
        """Send push notification to a single user."""
        from src.api.routes.push_notifications import NotificationLog, NotificationPreference, PushSubscription

        results: list[dict[str, Any]] = []

        result = await self.db.execute(
            select(NotificationPreference).filter(
                NotificationPreference.user_id == user_id  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        prefs = result.scalars().first()

        if prefs and not prefs.push_enabled:
            return [{"status": "skipped", "reason": "Push notifications disabled"}]

        result = await self.db.execute(
            select(PushSubscription).filter(
                PushSubscription.user_id == user_id,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                PushSubscription.is_active == True,  # type: ignore[attr-defined]  # noqa: E712  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        subscriptions = result.scalars().all()

        if not subscriptions:
            return [{"status": "skipped", "reason": "No active subscriptions"}]

        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "icon": "/icons/icon-192x192.png",
                "badge": "/icons/badge-72x72.png",
                "url": url or "/portal",
                "tag": notification_type,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        for sub in subscriptions:
            try:
                send_result = await self._send_web_push(sub, payload)
                results.append(send_result)

                log = NotificationLog(
                    user_id=user_id,
                    subscription_id=sub.id,
                    notification_type=notification_type,
                    title=title,
                    body=body,
                    data=data,
                    channel="push",
                    status="sent" if send_result.get("success") else "failed",
                    error_message=send_result.get("error"),
                    sent_at=datetime.utcnow(),
                )
                self.db.add(log)

            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(
                    "Push notification delivery failed [user_id=%s, subscription=%s]: %s: %s",
                    user_id,
                    sub.id,
                    type(e).__name__,
                    str(e)[:200],
                    exc_info=True,
                )
                results.append({"success": False, "error": str(e)})

        await self.db.commit()
        return results

    async def _send_web_push(self, subscription: Any, payload: str) -> dict[str, Any]:
        """Send actual Web Push message using pywebpush."""
        try:
            from pywebpush import webpush  # type: ignore[import-untyped]  # TYPE-IGNORE: MYPY-OVERRIDE

            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh_key,
                    "auth": subscription.auth_key,
                },
            }

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )

            subscription.last_used_at = datetime.utcnow()
            return {"success": True, "endpoint": subscription.endpoint}

        except ImportError:
            return {"success": True, "endpoint": subscription.endpoint, "simulated": True}

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(
                "Web push send failed [endpoint=%s]: %s: %s",
                subscription.endpoint[:80],
                type(e).__name__,
                str(e)[:200],
                exc_info=True,
            )
            error_msg = str(e)
            if "410" in error_msg or "404" in error_msg:
                subscription.is_active = False
            return {"success": False, "error": error_msg}

    async def send_bulk_notification(
        self,
        user_ids: list[int],
        title: str,
        body: str,
        url: str | None = None,
        data: dict | None = None,
        notification_type: str = "general",
    ) -> dict[str, Any]:
        """Send notification to multiple users."""
        results: dict[str, int] = {"sent": 0, "failed": 0, "skipped": 0}

        for user_id in user_ids:
            user_results = await self.send_notification(
                user_id=user_id,
                title=title,
                body=body,
                url=url,
                data=data,
                notification_type=notification_type,
            )

            for r in user_results:
                if r.get("success"):
                    results["sent"] += 1
                elif r.get("status") == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

        return results

    async def send_to_all(
        self,
        title: str,
        body: str,
        url: str | None = None,
        data: dict | None = None,
        notification_type: str = "general",
    ) -> dict[str, Any]:
        """Send notification to all users with active subscriptions."""
        from src.api.routes.push_notifications import PushSubscription

        sub_result = await self.db.execute(
            select(PushSubscription).filter(
                PushSubscription.is_active == True,  # type: ignore[attr-defined]  # noqa: E712  # TYPE-IGNORE: MYPY-OVERRIDE
                PushSubscription.user_id.isnot(None),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        subscriptions = sub_result.scalars().all()
        user_ids = list(set(int(s.user_id) for s in subscriptions if s.user_id))

        return await self.send_bulk_notification(
            user_ids=user_ids,
            title=title,
            body=body,
            url=url,
            data=data,
            notification_type=notification_type,
        )

    async def send_test(self, user_id: int) -> dict[str, Any]:
        """Send a test push notification to a user."""
        results = await self.send_notification(
            user_id=user_id,
            title="Test Notification",
            body="This is a test notification from QGP. If you see this, push notifications are working!",
            url="/dashboard",
            notification_type="test",
        )
        return {
            "success": any(r.get("success") for r in results),
            "results": results,
        }
