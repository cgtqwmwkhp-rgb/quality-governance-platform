"""Unit tests for Wave5 partner webhook scaffold."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.partner_webhook import (
    PARTNER_WEBHOOK_EVENTS,
    WebhookDeliveryLog,
    WebhookDeliveryStatus,
    WebhookSubscription,
)
from src.domain.services.partner_webhook_service import (
    PartnerWebhookService,
    build_signed_headers,
    sign_webhook_payload,
)

MIGRATION = Path("alembic/versions/20260716_partner_webhooks.py")


def test_event_catalog_contains_v1_events():
    assert PARTNER_WEBHOOK_EVENTS == (
        "inspection.started",
        "inspection.completed",
        "finding.created",
        "finding.updated",
        "capa.created",
        "capa.status_changed",
    )


def test_webhook_subscription_orm_columns():
    assert WebhookSubscription.__tablename__ == "webhook_subscriptions"
    assert WebhookSubscription.__table__.c.tenant_id.nullable is False
    assert WebhookSubscription.__table__.c.url.nullable is False
    assert WebhookSubscription.__table__.c.secret.nullable is False
    assert WebhookSubscription.__table__.c.events.nullable is False
    index_names = {index.name for index in WebhookSubscription.__table__.indexes}
    assert "ix_webhook_subscriptions_tenant_active" in index_names


def test_webhook_delivery_log_orm_columns():
    assert WebhookDeliveryLog.__tablename__ == "webhook_delivery_logs"
    assert WebhookDeliveryLog.__table__.c.subscription_id.nullable is False
    assert WebhookDeliveryLog.__table__.c.event_type.nullable is False
    assert WebhookDeliveryLog.__table__.c.payload.nullable is False
    fk = next(iter(WebhookDeliveryLog.__table__.c.subscription_id.foreign_keys))
    assert fk.ondelete and fk.ondelete.upper() == "CASCADE"


def test_partner_webhooks_migration_scaffold():
    assert MIGRATION.is_file()
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260716_partner_webhooks"' in text
    assert 'down_revision: Union[str, Sequence[str], None] = "20260716_capa_inv_src"' in text
    assert "webhook_subscriptions" in text
    assert "webhook_delivery_logs" in text
    assert "Wave2a" in text or "#1009" in text


def test_sign_webhook_payload_hmac_sha256():
    secret = "test-secret-key-16b"
    payload = b'{"event":"inspection.started","id":1}'
    timestamp = "1710000000"
    expected_message = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), expected_message, hashlib.sha256).hexdigest()
    assert sign_webhook_payload(secret, payload, timestamp) == expected


def test_build_signed_headers_includes_timestamp_and_signature():
    secret = "test-secret-key-16b"
    payload = {"event": "finding.created", "id": 42}
    headers = build_signed_headers(secret, payload, timestamp="1710000001")
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Partner-Timestamp"] == "1710000001"
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert headers["X-Partner-Signature"] == sign_webhook_payload(secret, body, "1710000001")


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


@pytest.mark.asyncio
async def test_record_delivery_creates_stubbed_log():
    db = AsyncMock()
    service = PartnerWebhookService(db)
    subscription = WebhookSubscription(
        id=1,
        tenant_id=10,
        url="https://partner.example/hooks",
        secret="test-secret-key-16b",
        events=["inspection.started"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payload = {"inspection_id": 99}
    log = await service.record_delivery(
        subscription=subscription,
        event_type="inspection.started",
        payload=payload,
        status=WebhookDeliveryStatus.STUBBED,
    )
    assert log.subscription_id == 1
    assert log.tenant_id == 10
    assert log.event_type == "inspection.started"
    assert log.status == WebhookDeliveryStatus.STUBBED
    assert log.signature is not None
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_stub_dispatch_rejects_inactive_subscription():
    db = AsyncMock()
    service = PartnerWebhookService(db)
    subscription = WebhookSubscription(
        id=1,
        tenant_id=10,
        url="https://partner.example/hooks",
        secret="test-secret-key-16b",
        events=["inspection.started"],
        is_active=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="inactive"):
        await service.stub_dispatch(
            subscription=subscription,
            event_type="inspection.started",
            payload={"id": 1},
        )


@pytest.mark.asyncio
async def test_stub_dispatch_rejects_unsubscribed_event():
    db = AsyncMock()
    service = PartnerWebhookService(db)
    subscription = WebhookSubscription(
        id=1,
        tenant_id=10,
        url="https://partner.example/hooks",
        secret="test-secret-key-16b",
        events=["finding.created"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="not subscribed"):
        await service.stub_dispatch(
            subscription=subscription,
            event_type="inspection.started",
            payload={"id": 1},
        )


@pytest.mark.asyncio
async def test_list_delivery_logs_returns_items_and_total():
    db = AsyncMock()
    log = WebhookDeliveryLog(
        id=5,
        subscription_id=1,
        tenant_id=10,
        event_type="capa.created",
        payload={"capa_id": 7},
        status=WebhookDeliveryStatus.STUBBED,
        created_at=datetime.now(timezone.utc),
    )
    db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(1),
            _ScalarsResult([log]),
        ]
    )
    service = PartnerWebhookService(db)
    items, total = await service.list_delivery_logs(10, subscription_id=1)
    assert total == 1
    assert items == [log]


@pytest.mark.asyncio
async def test_create_subscription_flushes_to_db():
    db = AsyncMock()
    service = PartnerWebhookService(db)
    sub = await service.create_subscription(
        tenant_id=10,
        url="https://partner.example/hooks",
        secret="test-secret-key-16b",
        events=["inspection.completed"],
        name="Partner A",
    )
    assert sub.tenant_id == 10
    assert sub.url == "https://partner.example/hooks"
    assert sub.events == ["inspection.completed"]
    db.add.assert_called_once()
    db.flush.assert_awaited()
