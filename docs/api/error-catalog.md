# API error catalog (D14 — Error handling & user-safe failures)

This document describes how the Quality Governance Platform API surfaces errors, how clients should react, and how resilience features (circuit breaker, fallbacks, metrics) fit together.

## Error envelope standard

Successful responses use each endpoint’s declared schema. **Errors** use a single JSON envelope so clients can parse failures consistently.

Shape:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable summary safe for display or logging",
    "details": {},
    "request_id": "correlation-id-for-support"
  }
}
```

| Field | Purpose |
|--------|---------|
| `code` | Stable machine-readable code from `ErrorCode` in `src/api/schemas/error_codes.py` (or an HTTP-derived default for generic `HTTPException`s). |
| `message` | Short explanation; should not leak stack traces or internal hostnames. |
| `details` | Optional structured context (field errors, tenant id, upstream hint). May be `{}`. |
| `request_id` | Same value as response header `X-Request-ID` when middleware has run; use in support tickets. |

Implementation reference: `src/api/middleware/error_handler.py` (`_build_envelope`).

## Error code catalog

The following table lists **every** code defined on `ErrorCode` in `src/api/schemas/error_codes.py`. HTTP status is the **typical** status used when this code is returned; some routes may map the same conceptual failure differently—always trust the response status.

| Code | HTTP | Description | User-safe message (example) | Recommended client action |
|------|------|-------------|-----------------------------|---------------------------|
| `ENTITY_NOT_FOUND` | 404 | Requested resource does not exist or is not visible. | “We couldn’t find that item.” | Do not retry; adjust URL or refresh list. |
| `DUPLICATE_ENTITY` | 409 | Create/update would violate uniqueness. | “This already exists.” | Do not retry same payload; show conflict and offer merge/edit. |
| `INVALID_STATE_TRANSITION` | 409 | Workflow/state machine rejects the transition. | “This action isn’t allowed in the current state.” | Do not retry; refresh entity and follow allowed transitions. |
| `VALIDATION_ERROR` | 422 | Request body/query failed validation (including FastAPI `RequestValidationError`). | “Please check the highlighted fields.” | Do not retry; fix validation `details.errors` and resubmit. |
| `FILE_VALIDATION_ERROR` | 422 | Uploaded file failed policy (type, size, content). | “That file couldn’t be accepted.” | Do not retry; choose a valid file. |
| `JSON_DEPTH_EXCEEDED` | 400 | JSON nesting/depth limits exceeded. | “The request data is too complex.” | Reduce payload complexity; do not retry as-is. |
| `PAYLOAD_TOO_LARGE` | 413 | Request body exceeds size limits. | “The upload is too large.” | Do not retry; compress or split content. |
| `MIME_TYPE_INVALID` | 415 | Wrong `Content-Type` or unsupported media. | “This type of file isn’t supported.” | Fix headers or format; do not retry blindly. |
| `AUTHENTICATION_REQUIRED` | 401 | Missing or invalid authentication. | “Please sign in to continue.” | Redirect to login or refresh token; one retry after refresh OK. |
| `TOKEN_EXPIRED` | 401 | Access or reset token expired. | “Your session expired—sign in again.” | Refresh token or re-authenticate; do not spam retries. |
| `TOKEN_REVOKED` | 401 | Token invalidated server-side. | “Your session is no longer valid.” | Force logout and re-login. |
| `INVALID_CREDENTIALS` | 401 | Wrong password or bad credential proof. | “Email or password isn’t correct.” | Do not retry rapidly; offer reset; backoff on brute force. |
| `ACCOUNT_LOCKED` | 403 | Account disabled/locked. | “Your account is locked—contact support.” | Do not retry; show support path. |
| `MFA_REQUIRED` | 403 | MFA challenge needed before access. | “Additional verification is required.” | Start MFA flow; do not retry same call without MFA. |
| `MFA_INVALID` | 401 | MFA code wrong or stale. | “That verification code didn’t work.” | Allow retry with new code; rate-limit UI. |
| `PASSWORD_TOO_WEAK` | 400 | Password policy not met. | “Choose a stronger password.” | Show policy hints from `details`; no network retry. |
| `PASSWORD_REUSED` | 400 | Password history / reuse policy violated. | “You can’t reuse that password.” | Prompt for a different password. |
| `PERMISSION_DENIED` | 403 | Authenticated but not allowed. | “You don’t have access to this.” | Do not retry; hide action or request role change. |
| `TENANT_ACCESS_DENIED` | 403 | Cross-tenant or tenant-scoped denial. | “You can’t access this organisation’s data.” | Switch tenant or request access. |
| `INSUFFICIENT_ROLE` | 403 | Missing required role/claim. | “You need a different role for this.” | Do not retry; escalate to admin. |
| `RATE_LIMIT_EXCEEDED` | 429 | Global or per-user rate limit hit. | “Too many requests—please wait.” | Honor `Retry-After`; exponential backoff. |
| `TENANT_QUOTA_EXCEEDED` | 429 | Tenant quota/limit exceeded. | “This organisation has hit a usage limit.” | Back off; contact tenant admin. |
| `EXTERNAL_SERVICE_ERROR` | 502 | Upstream dependency failed after retries/breaker logic. | “A connected service failed—try again shortly.” | Limited retry per policy; show generic error. |
| `EXTERNAL_SERVICE_TIMEOUT` | 504 | Upstream dependency timed out. | “A request to another system timed out.” | Retry per 5xx/timeout policy; avoid tight loops. |
| `CIRCUIT_BREAKER_OPEN` | 503 | Calls short-circuited while dependency is unhealthy. | “This feature is temporarily unavailable.” | Back off; retry later; optional “Try again” button. |
| `GDPR_ERROR` | 400 | GDPR/compliance constraint violated. | “This action isn’t allowed for data protection reasons.” | Do not retry; clarify with user/support. |
| `GDPR_ERASURE_PENDING` | 409 | Erasure/export workflow conflict. | “A privacy request is in progress for this data.” | Refresh state; follow compliance workflow. |
| `DATA_RETENTION_VIOLATION` | 400 | Retention rules block operation. | “This record can’t be changed due to retention rules.” | Do not retry; explain retention. |
| `IDEMPOTENCY_CONFLICT` | 409 | Same `Idempotency-Key` reused with different body. | “This request was already made with different data.” | Use new key or replay exact payload. |
| `INTERNAL_ERROR` | 500 | Unexpected server failure (logged server-side). | “Something went wrong on our side.” | Retry once per 5xx policy; include `request_id` if reporting. |
| `DATABASE_ERROR` | 500 / 503 | Primary DB failure or unrecoverable query error. | “We couldn’t complete that action.” | Treat as 5xx for retry policy; escalate if persistent. |
| `CONFIGURATION_ERROR` | 500 | Misconfiguration detected at runtime. | “This service isn’t configured correctly.” | No client retry; operations must fix deployment. |

Domain-layer defaults for several of these codes live in `src/domain/exceptions.py` (`DomainError` subclasses).

## Retry policy (client)

Apply retries **only** to safe, idempotent requests unless the product explicitly allows otherwise.

| Condition | Policy |
|-----------|--------|
| **429 (rate limited)** | Read `Retry-After` when present (seconds or HTTP-date). Wait at least that long, then retry with **exponential backoff** and jitter for subsequent 429s. |
| **503 (service unavailable)** | Retry up to **3** times with delays **1s → 2s → 4s** (plus small jitter). If still failing, show a stable error and optional “Retry” control. |
| **5xx (server error)** | Retry **once** after **2s**. If the second attempt fails, stop automatic retries and show a user-facing error with `request_id`. |
| **4xx (client error)** | **Do not** auto-retry. Show a **user-friendly** message derived from `error.message` and any structured `details` (e.g. validation field list). |

**Note:** `POST` with side effects should only retry if `Idempotency-Key` is used and the client can safely replay the same payload.

## Circuit breaker integration

The circuit breaker implementation lives in **`src/infrastructure/resilience/circuit_breaker.py`** (exported via `src/infrastructure/resilience/__init__.py`).

### Behaviour

- Each breaker has a **name** and is registered in a process-wide registry (`get_all_circuits()`).
- After **`failure_threshold`** consecutive failures (default **5**), the breaker moves to **OPEN** and **rejects new calls immediately** with `CircuitBreakerOpenError` instead of hammering the dependency.
- After **`recovery_timeout`** seconds (default **60**), the breaker allows a **half-open** probe (`half_open_max_calls`, default **1**). Success **closes** the circuit; failure **reopens** it.
- State transitions emit metrics via `track_metric` (e.g. `circuit_breaker.<name>.transition`, `circuit_breaker.<name>.state`, `circuit_breaker.<name>.total_failures`) in `src/infrastructure/monitoring/azure_monitor.py`.

### Protecting external calls (PAMS, email, SMS)

Use **named** breakers per integration (e.g. `pams`, `smtp`, `sms`) and wrap only the **outbound** call inside `await breaker.call(...)`. When the breaker is open, map the failure to API code **`CIRCUIT_BREAKER_OPEN`** (503) or **`EXTERNAL_SERVICE_ERROR`** (502) depending on whether you want to express “shaped outage” vs “upstream error,” and always return the standard **error envelope**.

The module also provides **`retry_with_backoff`** for transient `ConnectionError` / `TimeoutError` / `OSError`—compose **retry around the call**, then **circuit breaker around the retried operation** so repeated failures trip the breaker.

*Email today:* `src/domain/services/email_service.py` uses **Tenacity** for SMTP retries; align breaker naming and metrics when wrapping SMTP. *PAMS:* vehicle checklist routes use cache-first and 503 on live failure (`src/api/routes/vehicle_checklists.py`); circuit breakers should wrap the live PAMS query path where added.

## Fallback strategies

| Scenario | Strategy |
|----------|----------|
| **PAMS unavailable** | Prefer **cached** checklist rows in PostgreSQL (`PAMSVanChecklistCache` / `PAMSVanChecklistMonthlyCache`). When serving cache due to outage or staleness, show a **“Data may be stale”** banner in the UI. Live PAMS reads return 503 with a safe message when unrecoverable. |
| **Redis unavailable** | **Idempotency middleware** skips Redis and passes the request through (`src/api/middleware/idempotency.py`). Rate limiting can fall back to in-memory behaviour (see rate limiter docs). Treat as: **no distributed cache**—serve from **PostgreSQL** and accept reduced deduplication/idempotency guarantees for that window. |
| **Email service down** | Do not drop compliance-critical notifications silently: **enqueue** outbound email work to **Celery** with a **dead-letter path** (DLQ). On provider recovery, **retry** queued tasks with backoff; surface admin alerts for DLQ depth. |

## Client-side error handling (UX)

| Error class | Suggested UX |
|-------------|----------------|
| **401** (`AUTHENTICATION_REQUIRED`, `TOKEN_*`, `INVALID_CREDENTIALS`, `MFA_INVALID`) | **Redirect** to login or token refresh; toast only for inline forms (“Session expired”). |
| **403** (`PERMISSION_DENIED`, `TENANT_ACCESS_DENIED`, `INSUFFICIENT_ROLE`, `MFA_REQUIRED`, `ACCOUNT_LOCKED`) | **Toast or inline alert**; no retry; hide/disable controls that will always fail. |
| **404** | Inline empty state or “Not found”; **no** toast spam on navigation. |
| **409** (`DUPLICATE_ENTITY`, `INVALID_STATE_TRANSITION`, `IDEMPOTENCY_CONFLICT`, `GDPR_ERASURE_PENDING`) | **Inline conflict** message; offer refresh or diff; no blind retry. |
| **422** (`VALIDATION_ERROR`, `FILE_VALIDATION_ERROR`) | **Inline field errors** from `details.errors`; focus first invalid field. |
| **413 / 415** | **Toast** with guidance to resize file or fix type. |
| **429** | **Toast** “Slow down”; respect `Retry-After`; disable submit briefly. |
| **502 / 503 / 504** (`EXTERNAL_SERVICE_*`, `CIRCUIT_BREAKER_OPEN`) | **Toast or banner** + optional **Retry** button (manual, not loop). |
| **500** (`INTERNAL_ERROR`, `DATABASE_ERROR`, `CONFIGURATION_ERROR`) | **Generic toast**; show “Reference: `<request_id>`” in support dialog; at most **one** auto-retry per retry policy. |

Always log or report **`error.request_id`** with user consent for support.

## Error monitoring

- **Metric:** `api.error_rate_5xx` — OpenTelemetry counter defined in `src/infrastructure/monitoring/azure_monitor.py` (`setup_telemetry` / `track_metric` map key `"api.error_rate_5xx"`).
- **Instrumentation:** Ensure 5xx responses increment this counter in your HTTP middleware or gateway layer as part of the observability backlog if not already wired for every path.
- **Alerting:** Treat **5xx rate > 1%** of total requests over a rolling window (e.g. 15 minutes) as **Priority 2 (P2)** — page on-call or open an incident per your runbook. Combine with latency and dependency (PAMS/Redis/DB) dashboards.

---

*Source of truth for codes:* `src/api/schemas/error_codes.py` · *Envelope:* `src/api/middleware/error_handler.py` · *Breaker:* `src/infrastructure/resilience/circuit_breaker.py` · *5xx metric:* `src/infrastructure/monitoring/azure_monitor.py`.
