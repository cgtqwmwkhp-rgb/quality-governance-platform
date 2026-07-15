"""Partner webhook subscription service — HMAC signing + delivery log (v1 stub dispatch)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.partner_webhook import (
    PARTNER_WEBHOOK_EVENTS,
    WebhookDeliveryLog,
    WebhookDeliveryStatus,
    WebhookSubscription,
)

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Partner-Signature"
TIMESTAMP_HEADER = "X-Partner-Timestamp"


def sign_webhook_payload(secret: str, payload: bytes, timestamp: str) -> str:
    """Return HMAC-SHA256 hex digest for partner webhook verification."""
    message = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_signed_headers(secret: str, payload: dict[str, Any], timestamp: Optional[str] = None) -> dict[str, str]:
    """Build outbound headers with timestamp + HMAC signature."""
    ts = timestamp or str(int(datetime.now(timezone.utc).timestamp()))
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = sign_webhook_payload(secret, body, ts)
    return {
        "Content-Type": "application/json",
        TIMESTAMP_HEADER: ts,
        SIGNATURE_HEADER: signature,
    }


class PartnerWebhookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_subscription(
        self,
        *,
        tenant_id: int,
        url: str,
        secret: str,
        events: list[str],
        name: Optional[str] = None,
        is_active: bool = True,
    ) -> WebhookSubscription:
        subscription = WebhookSubscription(
            tenant_id=tenant_id,
            name=name,
            url=str(url),
            secret=secret,
            events=events,
            is_active=is_active,
        )
        self.db.add(subscription)
        await self.db.flush()
        return subscription

    async def list_subscriptions(self, tenant_id: int) -> list[WebhookSubscription]:
        result = await self.db.execute(
            select(WebhookSubscription)
            .where(WebhookSubscription.tenant_id == tenant_id)
            .order_by(WebhookSubscription.id.desc())
        )
        return list(result.scalars().all())

    async def get_subscription(self, tenant_id: int, subscription_id: int) -> Optional[WebhookSubscription]:
        result = await self.db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.id == subscription_id,
                WebhookSubscription.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_subscription(
        self,
        subscription: WebhookSubscription,
        *,
        name: Optional[str] = None,
        url: Optional[str] = None,
        secret: Optional[str] = None,
        events: Optional[list[str]] = None,
        is_active: Optional[bool] = None,
    ) -> WebhookSubscription:
        if name is not None:
            subscription.name = name
        if url is not None:
            subscription.url = str(url)
        if secret is not None:
            subscription.secret = secret
        if events is not None:
            subscription.events = events
        if is_active is not None:
            subscription.is_active = is_active
        await self.db.flush()
        return subscription

    async def delete_subscription(self, subscription: WebhookSubscription) -> None:
        await self.db.delete(subscription)
        await self.db.flush()

    async def record_delivery(
        self,
        *,
        subscription: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
        status: WebhookDeliveryStatus = WebhookDeliveryStatus.STUBBED,
        http_status: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> WebhookDeliveryLog:
        """Record a delivery attempt. v1 stubs outbound HTTP — no external send."""
        headers = build_signed_headers(subscription.secret, payload)
        signature = headers[SIGNATURE_HEADER]
        now = datetime.now(timezone.utc)
        log = WebhookDeliveryLog(
            subscription_id=subscription.id,
            tenant_id=subscription.tenant_id,
            event_type=event_type,
            payload=payload,
            status=status,
            http_status=http_status,
            error_message=error_message,
            signature=signature,
            created_at=now,
            delivered_at=now if status == WebhookDeliveryStatus.DELIVERED else None,
        )
        self.db.add(log)
        await self.db.flush()
        logger.info(
            "partner_webhook_delivery_recorded",
            extra={
                "subscription_id": subscription.id,
                "tenant_id": subscription.tenant_id,
                "event_type": event_type,
                "status": status.value,
            },
        )
        return log

    async def stub_dispatch(
        self,
        *,
        subscription: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
    ) -> WebhookDeliveryLog:
        """v1 stub: sign payload and record delivery without HTTP send."""
        if event_type not in PARTNER_WEBHOOK_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")
        if not subscription.is_active:
            raise ValueError("Subscription is inactive")
        if event_type not in subscription.events:
            raise ValueError(f"Subscription not subscribed to event: {event_type}")
        return await self.record_delivery(
            subscription=subscription,
            event_type=event_type,
            payload=payload,
            status=WebhookDeliveryStatus.STUBBED,
        )

    async def list_delivery_logs(
        self,
        tenant_id: int,
        *,
        subscription_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WebhookDeliveryLog], int]:
        query = select(WebhookDeliveryLog).where(WebhookDeliveryLog.tenant_id == tenant_id)
        count_query = select(func.count(WebhookDeliveryLog.id)).where(WebhookDeliveryLog.tenant_id == tenant_id)
        if subscription_id is not None:
            query = query.where(WebhookDeliveryLog.subscription_id == subscription_id)
            count_query = count_query.where(WebhookDeliveryLog.subscription_id == subscription_id)
        total_result = await self.db.execute(count_query)
        total = int(total_result.scalar() or 0)
        result = await self.db.execute(query.order_by(WebhookDeliveryLog.id.desc()).offset(skip).limit(limit))
        return list(result.scalars().all()), total
