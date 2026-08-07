# Partner OpenAPI — R6 API Reference

Partner integration surface for the Quality Governance Platform. All routes are tenant-scoped and served under `/api/v1`.

## Authentication

### Admin session (token management)

Partner API token CRUD requires an authenticated tenant admin JWT with `admin:manage`.

```
Authorization: Bearer <session_jwt>
```

### Partner bearer token (inbound API)

Tokens created via `/partner-auth/tokens` use the `qgp_pt_` prefix. Store the plaintext secret immediately — it is shown **once** on create.

```
Authorization: Bearer qgp_pt_<secret>
```

Supported scopes:

| Scope | Purpose |
|-------|---------|
| `webhooks:manage` | Manage webhook subscriptions |
| `inspections:read` | Read inspection data (reserved for R6+ emitters) |
| `documents:read` | Read library documents + signed URLs; document content/semantic search |
| `search:read` | Global search (`GET /api/v1/search/`), document modules only |
| `policies:read` | Allowlisted only. Reaches nothing today — see below |

#### Inbound routes that accept a partner bearer

A route accepts a partner token only if it opts in by name. Everything else
refuses one with `401`, including routes a session user reaches with the same
RBAC permission the scope maps to. The opt-in — not the scope — is what decides
reachability.

| Method | Path | Required partner scope |
|--------|------|------------------------|
| `GET` | `/api/v1/search/` | `search:read` |
| `GET` | `/api/v1/documents/search/semantic` | `documents:read` |
| `GET` | `/api/v1/documents/search/content` | `documents:read` |
| `GET` | `/api/v1/documents/{id}` | `documents:read` |
| `GET` | `/api/v1/documents/{id}/signed-url` | `documents:read` |

The published OpenAPI document carries the same fact per operation as
`x-qgp-partner-scope`, so this table is checkable rather than a claim.

`POST /api/v1/search/interpret` is **not** partner-callable. It bills an LLM call
per request and the integration does not need it.

#### Failure modes

| Condition | Status |
|-----------|--------|
| No `Authorization` header | `403` (bearer scheme) |
| Unknown, malformed, or revoked `qgp_pt_` token | `401` |
| Route does not accept partner tokens | `401` |
| Valid token, route accepts partner tokens, scope not granted | `403` |

`401` is deliberately identical for "no such token" and "route not partner-callable":
distinguishing them would make the endpoint an oracle for both the route list and
the validity of a guessed secret.

#### What a partner token can actually read

- **Tenant.** Bound from the token row, never from a request header or parameter.
  The same PostgreSQL RLS GUC a session user gets is bound for a partner caller.
- **Superuser.** Never. Every superuser exemption in the Document Library —
  including the cross-tenant single-document read — stays shut.
- **Library classification.** `documents:read` maps onto the platform's
  `document:read` permission and nothing else, so a partner reaches `all_staff`
  documents only. The `managers` and `restricted` tiers require `document:update`,
  `admin:manage` or a per-taxonomy permission, none of which any scope grants.
- **Global search.** `search:read` reaches the `Documents` and `Document Content`
  modules only. Global search also spans incidents, near misses, RTAs,
  complaints, risks, audit findings and actions; those are scoped by tenant but
  gated by no permission, so serving them to a long-lived bearer held in a
  third-party system would hand it the tenant's whole confidential estate. Those
  modules are not queried at all for a partner caller. A session user's reach
  here is unchanged.
- **`Document Content` in global search** additionally needs `documents:read`, so
  a `search:read`-only token sees document titles but no chunk text.
- **`policies:read`** grants no permission and opens no route. It is allowlisted
  so a token can be minted ahead of a policy surface that opts in.

#### Audit trail

A partner caller has no user id, so `library_document_access_logs.user_id` and
`document_search_logs.user_id` are `NULL` and `user_name` reads
`Partner: <token name>`. Partner activity is therefore distinguishable from a
person's in the audit trail rather than blended into it.

`last_used_at` on the token row is advanced best-effort: it is written in the
request's own transaction and so does not advance on a request that never
commits. It is credential-hygiene telemetry, not an authorisation input.

JWT session callers on all of the routes above keep their existing authorisation
unchanged (`document:read` where it was already required; authenticated-only
elsewhere). Existing tokens without the new scopes keep working for prior
surfaces.

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
  "scopes": ["documents:read", "search:read"]
}
```

**Response `201`**

```json
{
  "id": 12,
  "tenant_id": 3,
  "name": "Acme ERP integration",
  "token_prefix": "qgp_pt_AbCdEfGh",
  "scopes": ["documents:read", "search:read"],
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

### Issuing the CRM Bid Writer token (staging)

Run as a tenant admin holding `admin:manage`, against the staging FQDN, for the
tenant the CRM instance serves. Grant both scopes: `search:read` alone returns
document titles with no chunk text.

```bash
# 1. Admin session JWT for the target tenant.
QGP=https://<staging-fqdn>
JWT=$(curl -sS -X POST "$QGP/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"<tenant-admin>","password":"<password>"}' | jq -r .access_token)

# 2. Mint the token. The plaintext secret is returned once and never again.
curl -sS -X POST "$QGP/api/v1/partner-auth/tokens" \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"name":"CRM Bid Writer (K4)","scopes":["documents:read","search:read"]}' \
  | jq '{id, token_prefix, scopes, token}'
```

Store the `token` value as `QGP_PARTNER_TOKEN` in the CRM staging configuration.
Keep the `id` and `token_prefix`: the prefix is what appears in
`GET /partner-auth/tokens`, and the `id` is what `DELETE` revokes.

Verify the grant before handing it over — the second call must be `403`, which is
what proves the opt-in is doing the deciding rather than the token being a
general-purpose credential:

```bash
TOK=qgp_pt_<secret>

# Expect 200.
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $TOK" "$QGP/api/v1/documents/search/content?q=fire%20safety"

# Expect 401 — the library list did not opt in to partner tokens.
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $TOK" "$QGP/api/v1/documents/"
```

To rotate: mint the replacement, deploy it to CRM, then `DELETE` the old `id`.
Revocation takes effect on the next request — `is_active` is checked on every
call, not cached.

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
    "message": "Unsupported scope(s): foo:bar. Allowed: webhooks:manage, inspections:read, documents:read, search:read, policies:read"
  }
}
```
