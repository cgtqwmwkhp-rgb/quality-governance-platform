# Partner Webhooks — Wave5/R6 Ops Runbook

## Overview

Partner webhooks let external systems receive signed HTTP callbacks when governance events occur. Wave5 v1 added subscription CRUD, HMAC signing, and delivery audit trail. **R6** adds scoped partner API tokens and replaces stub dispatch with signed HTTP delivery via Celery + httpx retries.

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

## Partner API Tokens (R6)

| Method | Path | Permission |
|--------|------|------------|
| `POST` | `/api/v1/partner-auth/tokens` | `admin:manage` |
| `GET` | `/api/v1/partner-auth/tokens` | `admin:manage` |
| `DELETE` | `/api/v1/partner-auth/tokens/{id}` | `admin:manage` |

- Tokens use prefix `qgp_pt_`; only SHA-256 hash is stored.
- Plaintext secret returned **once** on create.
- Scopes: `webhooks:manage`, `inspections:read`.
- Revoke is idempotent (`is_active=false`, `revoked_at` set).

See `docs/api/partner-openapi.md` for example payloads.

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

## Delivery (R6)

`PartnerWebhookService.dispatch_event`:

1. Validates subscription + event type
2. Persists delivery log with `pending` status + signature
3. Enqueues `deliver_partner_webhook` Celery task

Celery task behaviour:

- **2xx** → log status `delivered`, `http_status` recorded
- **4xx** → log status `failed`, no retry
- **5xx / network / timeout** → Celery retry (max 3), then `failed`

```
GET /api/v1/partner-webhooks/deliveries?subscription_id={id}
```

Statuses: `pending`, `delivered`, `failed` (legacy `stubbed` on pre-R6 rows).

## Database

Migrations (in order):

1. `20260716_partner_webhooks` — `webhook_subscriptions`, `webhook_delivery_logs`
2. `20260717_partner_api_tokens` — `partner_api_tokens`

## Rollback

1. Revert PR
2. `alembic downgrade 20260716_partner_webhooks`

## Future (R6+)

- Wire event emitters from inspection/finding/CAPA domain services
- Partner bearer auth middleware for inbound partner API routes
- Dead-letter queue integration for exhausted retries
