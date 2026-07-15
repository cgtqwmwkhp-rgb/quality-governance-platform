# Partner OpenAPI — R6 API Reference

Partner integration surface for the Quality Governance Platform. All routes are tenant-scoped and served under `/api/v1`.

## Authentication

### Admin session (token management)

Partner API token CRUD requires an authenticated tenant admin JWT with `admin:manage`.

```
Authorization: Bearer <session_jwt>
```

### Partner bearer token (future inbound API)

Tokens created via `/partner-auth/tokens` use the `qgp_pt_` prefix. Store the plaintext secret immediately — it is shown **once** on create.

```
Authorization: Bearer qgp_pt_<secret>
```

Supported scopes:

| Scope | Purpose |
|-------|---------|
| `webhooks:manage` | Manage webhook subscriptions |
| `inspections:read` | Read inspection data (reserved for R6+ emitters) |

---

## Partner API Tokens

### Create token

```
POST /api/v1/partner-auth/tokens
```

**Request**

```json
{
  "name": "Acme ERP integration",
  "scopes": ["webhooks:manage", "inspections:read"]
}
```

**Response `201`**

```json
{
  "id": 12,
  "tenant_id": 3,
  "name": "Acme ERP integration",
  "token_prefix": "qgp_pt_AbCdEfGh",
  "scopes": ["webhooks:manage", "inspections:read"],
  "is_active": true,
  "last_used_at": null,
  "revoked_at": null,
  "created_at": "2026-07-17T10:00:00Z",
  "updated_at": "2026-07-17T10:00:00Z",
  "token": "qgp_pt_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
}
```

### List tokens

```
GET /api/v1/partner-auth/tokens?include_revoked=false
```

**Response `200`**

```json
{
  "items": [
    {
      "id": 12,
      "tenant_id": 3,
      "name": "Acme ERP integration",
      "token_prefix": "qgp_pt_AbCdEfGh",
      "scopes": ["webhooks:manage"],
      "is_active": true,
      "last_used_at": null,
      "revoked_at": null,
      "created_at": "2026-07-17T10:00:00Z",
      "updated_at": "2026-07-17T10:00:00Z"
    }
  ],
  "total": 1
}
```

### Revoke token

```
DELETE /api/v1/partner-auth/tokens/{token_id}
```

**Response `200`**

```json
{
  "id": 12,
  "tenant_id": 3,
  "name": "Acme ERP integration",
  "token_prefix": "qgp_pt_AbCdEfGh",
  "scopes": ["webhooks:manage"],
  "is_active": false,
  "last_used_at": null,
  "revoked_at": "2026-07-17T11:30:00Z",
  "created_at": "2026-07-17T10:00:00Z",
  "updated_at": "2026-07-17T11:30:00Z"
}
```

---

## Partner Webhooks

### Event catalog

```
GET /api/v1/partner-webhooks/events
```

**Response**

```json
{
  "events": [
    "inspection.started",
    "inspection.completed",
    "finding.created",
    "finding.updated",
    "capa.created",
    "capa.status_changed"
  ]
}
```

### Create subscription

```
POST /api/v1/partner-webhooks/subscriptions
```

**Request**

```json
{
  "name": "Acme webhook",
  "url": "https://partner.example/hooks/qgp",
  "secret": "whsec_minimum_16_chars",
  "events": ["inspection.completed", "finding.created"],
  "is_active": true
}
```

### Outbound webhook payload (partner receives)

When an event is dispatched, the platform POSTs signed JSON:

**Headers**

```
Content-Type: application/json
X-Partner-Timestamp: 1710000001
X-Partner-Signature: <hmac_sha256_hex>
```

**Body**

```json
{
  "event": "inspection.completed",
  "inspection_id": 4421,
  "completed_at": "2026-07-17T09:15:00Z"
}
```

**Signature verification**

```
message = "{timestamp}.{canonical_json_body}"
signature = HMAC-SHA256(subscription_secret, message)  # hex digest
```

Canonical JSON uses sorted keys and compact separators (`,`, `:`).

### Delivery logs

```
GET /api/v1/partner-webhooks/deliveries?subscription_id=7
```

Statuses: `pending`, `delivered`, `failed` (legacy `stubbed` may appear on pre-R6 rows).

R6 enqueues signed HTTP delivery via Celery (`deliver_partner_webhook`) with retries on network/5xx errors.

---

## Error envelope

Validation and not-found errors use the platform standard:

```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "Unsupported scope(s): foo:bar. Allowed: webhooks:manage, inspections:read"
  }
}
```
