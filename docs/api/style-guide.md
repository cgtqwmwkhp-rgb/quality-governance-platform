# API style guide

This document describes how the Quality Governance Platform HTTP API is structured in code. It is derived from the FastAPI application, shared utilities, and OpenAPI baseline—not generic REST guidance.

---

## 1. URL conventions

### Prefix and versioning

All application routers are mounted under a single versioned prefix:

- **Base path:** `/api/v1` (`app.include_router(api_router, prefix="/api/v1")` in `src/main.py`).

Some endpoints are registered on the app outside that router (for example `/health`, `/healthz`, `/readyz`, and `/api/v1/meta/version`), but the bulk of the product API lives under `/api/v1`.

### Resource naming

Sub-routers are included with path prefixes in `src/api/__init__.py`. Conventions observed there include:

- **Plural or collection-oriented segments** for domains: `/users`, `/incidents`, `/standards`, `/audits`, `/documents`, `/notifications`, `/vehicles`, `/drivers`, etc.
- **Kebab-case** for multi-word paths: `/audit-templates`, `/xml-import`, `/risk-register`, `/near-misses`, `/vehicle-checklists`, `/document-control`, `/compliance-automation`, `/evidence-assets`, `/policy-acknowledgment` modules use hyphenated paths.
- **Nested conceptual paths** where appropriate (e.g. `/vehicle-checklists/analytics`).

### Trailing slashes

The app is configured with **`redirect_slashes=False`** so clients should use the canonical path as documented (avoid relying on automatic slash redirects, especially behind proxies).

### OpenAPI contract

`openapi-baseline.json` is a large JSON document whose top-level structure includes `components.schemas` with schema definitions; field names in those schemas use **snake_case** (for example `acknowledgment_type`, `due_within_days`), consistent with Pydantic models exposed as JSON.

---

## 2. HTTP methods and their semantics

### Allowed methods (CORS)

`CORSMiddleware` in `src/main.py` allows: **GET, POST, PUT, PATCH, DELETE, OPTIONS**.

### Typical usage in routes

Route modules use FastAPI decorators in the usual way—for example `src/api/routes/incidents.py`:

- **POST `/`** on a resource router → create (returns **201 Created** where specified, e.g. `create_incident`).
- **GET `/{id}`** → read a single resource.
- **GET `/`** → list collection (often with query parameters).

Exact status codes and bodies are defined per endpoint; common error status codes used alongside `HTTPException` in incidents include **403**, **404**, **409**, **500**, and **503**.

---

## 3. Pagination

### Shared model (`src/core/pagination.py`)

- **`PaginationInput`:** `page` (default 1, minimum 1), `page_size` (default 20, clamped between 1 and 500). Computes `offset = (page - 1) * page_size`.
- **`PaginatedResponse`:** JSON envelope fields:
  - `items` — list of results  
  - `total` — total row count  
  - `page` — current page  
  - `page_size` — page size  
  - `pages` — total number of pages (0 if `total` is 0)

`paginate()` runs a count query and applies `offset`/`limit` to the main query.

### FastAPI query binding (`src/api/utils/pagination.py`)

`PaginationParams` subclasses `PaginationInput` and binds query parameters via FastAPI `Query`:

- **`page`:** default `1`, `ge=1`  
- **`page_size`:** default `20`, `ge=1`, `le=500`

### Endpoint-level overrides

Individual routes may declare their own `Query` limits instead of using `PaginationParams`. For example, `list_incidents` in `src/api/routes/incidents.py` uses **`page_size` default 50 with `le=100`**, then constructs `PaginationParams(page=page, page_size=page_size)` for the service layer—so **defaults and max page size can differ by endpoint** even when the same `PaginatedResponse` shape is returned.

**Client expectation:** always send **`page`** and **`page_size`** as query parameters when listing unless the endpoint documents different names; expect a body shaped like `PaginatedResponse` when the response model is list-style pagination.

---

## 4. Error response format

### Handler envelope (canonical)

Global handlers in `src/api/middleware/error_handler.py` normalize failures to a single JSON shape:

```json
{
  "error": {
    "code": "<string>",
    "message": "<string>",
    "details": {},
    "request_id": "<string>"
  }
}
```

- **`request_id`** comes from `request.state.request_id`, or a newly generated UUID if missing (`getattr(request.state, "request_id", None) or str(uuid.uuid4())`).
- **`details`** is an object; for validation errors it includes structured `errors` (see below).

### Route-level `detail` helper

`api_error()` in `src/api/utils/errors.py` builds the **inner** fields used as `HTTPException` detail:

```python
{"code": "...", "message": "...", "details": {}}
```

The exception handler’s `_normalize_http_detail()` accepts this dict (or nested `{"error": {...}}`) and still emits the **outer** `error` object with **`request_id`** added by `_build_envelope()`.

### Validation (422)

`RequestValidationError` is mapped to **422** with `ErrorCode.VALIDATION_ERROR`, message `"Request validation failed"`, and `details.errors` as a list of `{field, message, type}` built from Pydantic/Starlette validation errors.

### Default code mapping by HTTP status

For plain `HTTPException`s without an explicit `api_error` payload, status-to-default-code mapping includes:

| Status | Default `code` |
|--------|------------------|
| 400 | `VALIDATION_ERROR` |
| 401 | `AUTHENTICATION_REQUIRED` |
| 403 | `PERMISSION_DENIED` |
| 404 | `ENTITY_NOT_FOUND` |
| 409 | `DUPLICATE_ENTITY` |
| 429 | `RATE_LIMIT_EXCEEDED` |
| 500 | `INTERNAL_ERROR` |

Other statuses fall back to a string like `HTTP_<status>`.

### Known deviations

- **Rate limiter 429** (`src/infrastructure/middleware/rate_limiter.py`) returns a JSON body with **`{"detail": "Rate limit exceeded..."}`** rather than the `error` envelope—clients should still rely on **429** and **`X-RateLimit-*`** headers (see §8).
- **Idempotency conflict** (`src/api/middleware/idempotency.py`) returns **`{"error": {"code": "IDEMPOTENCY_CONFLICT", ...}}`** without **`request_id`** in that middleware-generated payload.

---

## 5. Error codes catalog

Structured codes are defined as string constants on **`ErrorCode`** in `src/api/schemas/error_codes.py`:

| Constant | Value |
|----------|--------|
| `ENTITY_NOT_FOUND` | `ENTITY_NOT_FOUND` |
| `DUPLICATE_ENTITY` | `DUPLICATE_ENTITY` |
| `INVALID_STATE_TRANSITION` | `INVALID_STATE_TRANSITION` |
| `VALIDATION_ERROR` | `VALIDATION_ERROR` |
| `FILE_VALIDATION_ERROR` | `FILE_VALIDATION_ERROR` |
| `JSON_DEPTH_EXCEEDED` | `JSON_DEPTH_EXCEEDED` |
| `PAYLOAD_TOO_LARGE` | `PAYLOAD_TOO_LARGE` |
| `MIME_TYPE_INVALID` | `MIME_TYPE_INVALID` |
| `AUTHENTICATION_REQUIRED` | `AUTHENTICATION_REQUIRED` |
| `TOKEN_EXPIRED` | `TOKEN_EXPIRED` |
| `TOKEN_REVOKED` | `TOKEN_REVOKED` |
| `INVALID_CREDENTIALS` | `INVALID_CREDENTIALS` |
| `ACCOUNT_LOCKED` | `ACCOUNT_LOCKED` |
| `MFA_REQUIRED` | `MFA_REQUIRED` |
| `MFA_INVALID` | `MFA_INVALID` |
| `PASSWORD_TOO_WEAK` | `PASSWORD_TOO_WEAK` |
| `PASSWORD_REUSED` | `PASSWORD_REUSED` |
| `PERMISSION_DENIED` | `PERMISSION_DENIED` |
| `TENANT_ACCESS_DENIED` | `TENANT_ACCESS_DENIED` |
| `INSUFFICIENT_ROLE` | `INSUFFICIENT_ROLE` |
| `RATE_LIMIT_EXCEEDED` | `RATE_LIMIT_EXCEEDED` |
| `TENANT_QUOTA_EXCEEDED` | `TENANT_QUOTA_EXCEEDED` |
| `EXTERNAL_SERVICE_ERROR` | `EXTERNAL_SERVICE_ERROR` |
| `EXTERNAL_SERVICE_TIMEOUT` | `EXTERNAL_SERVICE_TIMEOUT` |
| `CIRCUIT_BREAKER_OPEN` | `CIRCUIT_BREAKER_OPEN` |
| `GDPR_ERROR` | `GDPR_ERROR` |
| `GDPR_ERASURE_PENDING` | `GDPR_ERASURE_PENDING` |
| `DATA_RETENTION_VIOLATION` | `DATA_RETENTION_VIOLATION` |
| `IDEMPOTENCY_CONFLICT` | `IDEMPOTENCY_CONFLICT` |
| `INTERNAL_ERROR` | `INTERNAL_ERROR` |
| `DATABASE_ERROR` | `DATABASE_ERROR` |
| `CONFIGURATION_ERROR` | `CONFIGURATION_ERROR` |

---

## 6. Authentication

### Scheme

`src/api/dependencies/__init__.py` uses FastAPI **`HTTPBearer`** (`security = HTTPBearer()`). Protected dependencies expect:

`Authorization: Bearer <JWT>`

Failed JWT validation raises **`HTTPException` with status `401`**, detail `"Could not validate credentials"`, and **`WWW-Authenticate: Bearer`**.

Azure token exchange and similar flows use **`api_error(ErrorCode.INVALID_CREDENTIALS, ...)`** with **401** and the same **`WWW-Authenticate: Bearer`** header where applicable (`src/api/routes/auth.py`).

### 401 vs 403 in this codebase

- **401 Unauthorized:** missing/invalid token, bad credentials, or unauthenticated access to a protected dependency (`get_current_user`).
- **403 Forbidden:** authenticated user fails a policy check—examples include disabled account (`"User account is disabled"`), inactive user, non-superuser hitting superuser-only routes, missing permission from `require_permission`, or business-rule denials that raise `PermissionError` mapped to **403** with `ErrorCode.PERMISSION_DENIED` (see `create_incident` in `incidents.py`).

**Optional auth:** `HTTPBearer(auto_error=False)` is used for `get_optional_current_user` so some routes can work anonymously but still accept a Bearer token when present.

---

## 7. Idempotency

`IdempotencyMiddleware` (`src/api/middleware/idempotency.py`) applies to **POST, PUT, and PATCH** when the client sends:

`Idempotency-Key: <client-chosen value>`

Behavior (when Redis is available):

- Caches successful response metadata and body for **24 hours** (TTL `86400` seconds).
- Keys are stored as `idem:<idempotency_key>`.
- Request bodies are hashed (SHA-256); if the same key is reused with a **different** payload, the API responds with **409** and code **`IDEMPOTENCY_CONFLICT`**.
- If Redis is unavailable, requests proceed **without** idempotency caching.

CORS in `src/main.py` explicitly allows the **`Idempotency-Key`** request header.

---

## 8. Rate limiting

`rate_limit_middleware` in `src/infrastructure/middleware/rate_limiter.py` documents response headers:

- **`X-RateLimit-Limit`** — maximum requests allowed in the window for this check  
- **`X-RateLimit-Remaining`** — remaining quota  
- **`X-RateLimit-Reset`** — Unix timestamp when the window resets  

On **429 Too Many Requests**, the middleware also sets **`Retry-After`** (seconds until retry).

The implementation uses a **60-second** window (`window_seconds=60`) with per-path `RateLimitConfig` (see `ENDPOINT_LIMITS` in the same file). Authenticated clients are detected via a **`Bearer`** token prefix on `Authorization` and receive **`authenticated_multiplier`** (default **2.0**) on the per-minute limit.

**Client visibility:** `CORSMiddleware` **`expose_headers`** in `src/main.py` includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After` so browsers can read them from cross-origin responses.

Health and readiness paths (`/health`, `/healthz`, `/readyz`, etc.) skip rate limiting.

---

## 9. Naming conventions

### JSON / Python field names

OpenAPI components and Pydantic models use **snake_case** for property names (evident in the first schemas of `openapi-baseline.json` and throughout route schemas).

### URL path segments

Path prefixes use **lowercase** and **kebab-case** for multi-word resources (`/audit-trail`, `/feature-flags`, etc.), as registered in `src/api/__init__.py`.

### Resource plurals

Collection routers are predominantly **plural** nouns (`/incidents`, `/users`, `/policies`). A few administrative or compound modules use descriptive paths (`/admin/config`, `/portal`).

### Request correlation

Clients may send **`X-Request-ID`**; `RequestStateMiddleware` (`src/core/middleware.py`) stores it on `request.state` and echoes it on responses as **`X-Request-ID`** (UUID hex if not provided). Dependencies can inject `request_id` via `get_request_id` (`src/api/dependencies/request_context.py`) for logging and audit—aligned with the **`request_id`** field in the standard error envelope.

---

## References (source files)

| Topic | Location |
|--------|-----------|
| App prefix, CORS, middleware order | `src/main.py` |
| Router prefixes | `src/api/__init__.py` |
| Error envelope & handlers | `src/api/middleware/error_handler.py` |
| `api_error` helper | `src/api/utils/errors.py` |
| Error code constants | `src/api/schemas/error_codes.py` |
| Pagination types | `src/core/pagination.py`, `src/api/utils/pagination.py` |
| JWT / Bearer dependencies | `src/api/dependencies/__init__.py` |
| Idempotency | `src/api/middleware/idempotency.py` |
| Rate limits & headers | `src/infrastructure/middleware/rate_limiter.py` |
| Request ID | `src/core/middleware.py`, `src/api/dependencies/request_context.py` |
| Example routes | `src/api/routes/incidents.py`, `src/api/routes/auth.py` |
| OpenAPI baseline | `openapi-baseline.json` |
