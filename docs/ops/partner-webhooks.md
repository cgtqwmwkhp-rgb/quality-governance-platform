# Partner Webhooks — Wave5 Ops Runbook

## Overview

Partner webhooks let external systems receive signed HTTP callbacks when governance events occur. Wave5 v1 is a **scaffold**: subscription CRUD, HMAC signing helper, delivery log persistence, and stub dispatch (no outbound HTTP in v1).

## Event Catalog (v1)

| Event | Description |
|-------|-------------|
| `inspection.started` | An audit/inspection run has started |
| `inspection.completed` | An audit/inspection run has completed |
| `finding.created` | A new audit finding was recorded |
| `finding.updated` | An existing audit finding was updated |
| `capa.created` | A CAPA action was created |
| `capa.status_changed` | A CAPA action status changed |

Query the catalog at runtime:

```
GET /api/v1/partner-webhooks/events
```

## Subscription Management

| Method | Path | Permission |
|--------|------|------------|
| `POST` | `/api/v1/partner-webhooks/subscriptions` | `admin:manage` |
| `GET` | `/api/v1/partner-webhooks/subscriptions` | authenticated tenant user |
| `GET` | `/api/v1/partner-webhooks/subscriptions/{id}` | authenticated tenant user |
| `PATCH` | `/api/v1/partner-webhooks/subscriptions/{id}` | `admin:manage` |
| `DELETE` | `/api/v1/partner-webhooks/subscriptions/{id}` | `admin:manage` |

Subscriptions are tenant-scoped. The `secret` is stored server-side and never returned in API responses.

## HMAC Signature Verification

Outbound payloads are signed with HMAC-SHA256:

```
message = "{timestamp}.{canonical_json_body}"
signature = HMAC-SHA256(secret, message)  # hex digest
```

Headers:

- `X-Partner-Timestamp` — Unix epoch seconds
- `X-Partner-Signature` — hex HMAC digest
- `Content-Type: application/json`

Partners should reject requests with timestamps older than 5 minutes (enforcement is partner-side in v1).

## Delivery Logs

```
GET /api/v1/partner-webhooks/deliveries?subscription_id={id}
```

Statuses: `pending`, `stubbed`, `delivered`, `failed`.

v1 records `stubbed` deliveries when `stub_dispatch` is invoked — no HTTP send occurs until Wave5b wires Celery/httpx delivery.

## Database

Migration: `20260716_partner_webhooks` (revises `20260716_capa_inv_src`)

Tables:

- `webhook_subscriptions` — tenant-scoped endpoint + event filter
- `webhook_delivery_logs` — immutable delivery attempt log (CASCADE on subscription delete)

## Rollback

1. Revert PR
2. `alembic downgrade 20260716_capa_inv_src`

## Future (Wave5b+)

- Wire event emitters from inspection/finding/CAPA domain services
- Replace stub dispatch with async httpx delivery + retries
- Dead-letter queue integration for failed deliveries
