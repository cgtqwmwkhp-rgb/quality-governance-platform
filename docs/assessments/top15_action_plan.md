# Top 15 Enhancement Action Plan

**Date:** 2026-03-07 (Post Week-1 Uplift, Post Re-Assessment)
**Method:** 3-round deep-dive across codebase, APIs, backend, frontend, workflows, structure, database
**Goal:** Move WCS from 7.1 → 8.5+ via low-effort, high-impact enhancements

---

## Assessment Rounds Summary

| Round | Focus | Key Findings |
|-------|-------|-------------|
| **Round 1** | Backend, APIs, codebase structure | Risk JSON column bug (data loss); routes bypass service layer; inconsistent pagination; no GZip; inconsistent errors |
| **Round 2** | Frontend UX, workflows, database | No breadcrumbs; `alert()` used for errors; no 429 handling; missing composite indexes; no state transition enforcement |
| **Round 3** | Cross-cutting integration | Global toast not wired to interceptor; health router not mounted; SoftDelete only on User; missing request logging |

---

## Tier 1 — Low Effort / High Value (Items 1–5)

### 1. Fix Risk Update JSON Column Name Bug — DATA LOSS BUG

| Field | Detail |
|-------|--------|
| **Impact** | **CRITICAL** — Updates to `clause_ids`, `control_ids`, `linked_audit_ids`, `linked_incident_ids` silently fail. Data is lost on every risk update. |
| **Evidence** | `src/api/routes/risks.py` L375-384: `setattr(risk, f"{field}_json", ...)` writes to `clause_ids_json`, `control_ids_json` etc. But `src/domain/models/risk.py` L66-74 defines the actual columns as `clause_ids_json_legacy`, `control_ids_json_legacy`, `linked_audit_ids_json_legacy`, `linked_incident_ids_json_legacy`. The `_json` suffix doesn't match the `_json_legacy` columns. Risk create (L182-185) correctly uses `_json_legacy`, so this bug is isolated to the update path. |
| **Effort** | **S** (10-minute fix) |
| **Fix** | Add a mapping dict in `risks.py` update handler to map schema field names to the correct `_legacy` column names. |
| **Dimensions** | D24 Data Integrity (+0.3), D10 API Quality (+0.2) |
| **Tests** | Integration test: `PATCH /api/v1/risks/{id}` with `clause_ids=[1,2]` → verify `clause_ids_json_legacy` column has `[1,2]` |
| **Rollback** | Revert mapping dict |

### 2. Add GZip Compression Middleware

| Field | Detail |
|-------|--------|
| **Impact** | JSON API responses for list endpoints (incidents, complaints, audits, risks) can be 50-200KB. GZip typically achieves 80-90% compression on JSON, reducing transfer time and bandwidth. |
| **Evidence** | `src/main.py` middleware chain (L231-274): no compression middleware. Starlette provides `GZipMiddleware` built-in. |
| **Effort** | **S** (5 lines) |
| **Fix** | Add `from starlette.middleware.gzip import GZipMiddleware` and `app.add_middleware(GZipMiddleware, minimum_size=1000)` to `src/main.py`. |
| **Dimensions** | D04 Performance (+0.3) |
| **Tests** | Integration test: response with `Accept-Encoding: gzip` returns `Content-Encoding: gzip` |
| **Rollback** | Remove middleware line |

### 3. Standardize Error Responses to Use `api_error()`

| Field | Detail |
|-------|--------|
| **Impact** | Frontend client receives mixed error shapes: plain strings from incidents/complaints, structured `{code, message, details}` from risks. Clients need different parsing logic per endpoint. |
| **Evidence** | `src/api/routes/incidents.py` L114-116: `detail=f"Incident with ID {incident_id} not found"` (plain string). `src/api/routes/risks.py` L40-42: `detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Risk not found")` (structured). Same pattern in complaints and other routes. |
| **Effort** | **S** (search-and-replace across route files) |
| **Fix** | Replace all `detail="string"` patterns with `detail=api_error(ErrorCode.*, "message")` across all route files. The `api_error` function and `ErrorCode` enum already exist in `src/api/schemas/error_codes.py`. |
| **Dimensions** | D10 API Quality (+0.3), D14 Error Handling (+0.2) |
| **Tests** | Contract test: all 404/409/403 responses have `{code, message}` structure |
| **Rollback** | Revert to plain strings |

### 4. Mount Health Router + Extend `/readyz` to Check Redis

| Field | Detail |
|-------|--------|
| **Impact** | The root `/readyz` in `main.py` (L364-381) only checks database. A richer implementation in `src/api/routes/health.py` (L31-77) checks both DB and Redis, but it's never mounted. Kubernetes may route traffic to instances with broken Redis — rate limiting, caching, and idempotency all fail silently. |
| **Evidence** | `src/main.py` L364-381: `/readyz` does `SELECT 1` only. `src/api/routes/health.py` has DB + Redis checks but is NOT in `src/api/__init__.py` (confirmed by grep). |
| **Effort** | **S** (add include_router or copy Redis check to main.py) |
| **Fix** | Option A: Add `from src.api.routes import health` and `api_router.include_router(health.router, tags=["Health"])` to `src/api/__init__.py`, then update `/readyz` in `main.py` to delegate to the health router. Option B: Copy the Redis check from `health.py` into the `/readyz` handler in `main.py`. |
| **Dimensions** | D05 Reliability (+0.3), D13 Observability (+0.2) |
| **Tests** | Integration test: `/readyz` returns Redis status; test with Redis unavailable → 503 |
| **Rollback** | Remove Redis check from readyz |

### 5. Add 429 Rate-Limit Handling to Frontend API Interceptor

| Field | Detail |
|-------|--------|
| **Impact** | The Axios interceptor in `frontend/src/api/client.ts` handles 401, 403, 409, 422, 500 — but NOT 429 (Too Many Requests). When rate-limited, users see a generic error instead of a helpful "slow down" message. No automatic retry with backoff. |
| **Evidence** | `frontend/src/api/client.ts` L322-432: response interceptor. No case for `status === 429`. Rate limiter returns 429 per `src/infrastructure/middleware/rate_limiter.py`. |
| **Effort** | **S** (add 429 case to interceptor + optional retry logic) |
| **Fix** | Add `else if (status === 429) { classifiedMessage = "Too many requests. Please wait a moment and try again."; }` to interceptor. Optionally: extract `Retry-After` header and auto-retry after delay. |
| **Dimensions** | D14 Error Handling (+0.2), D02 UX Quality (+0.2) |
| **Tests** | Unit test: mock 429 response → verify classifiedMessage set correctly |
| **Rollback** | Remove 429 case |

---

## Tier 2 — Critical Workflows (Items 6–10)

### 6. Enforce Status Transition Validation on Incident/Audit/Risk Updates

| Field | Detail |
|-------|--------|
| **Impact** | No server-side validation of status transitions. Any status can be set to any other status via PATCH — e.g., "Closed" → "Reported" on incidents, "completed" → "draft" on audit runs. This bypasses workflow integrity and corrupts audit trails. |
| **Evidence** | `src/api/routes/incidents.py`: PATCH handler accepts any `status` value without checking current state. `src/domain/models/incident.py` L37: defines `IncidentStatus` enum but no `VALID_TRANSITIONS` map. Same pattern in complaints, risks, audit runs. No `StateTransitionError` raised anywhere in route handlers (the exception class exists in `src/domain/exceptions.py` but is unused in routes). |
| **Effort** | **M** |
| **Fix** | Add a `VALID_TRANSITIONS: dict[Status, set[Status]]` to each status enum. Create a `validate_transition(current, new)` helper that raises `StateTransitionError`. Call it in each PATCH handler before setting status. |
| **Dimensions** | D24 Data Integrity (+0.3), D21 Code Quality (+0.2) |
| **Tests** | Unit test per module: valid transition → 200; invalid transition → 409 with `StateTransitionError` |
| **Rollback** | Remove transition check |

### 7. Wire Incident/Complaint Routes Through Service Layer

| Field | Detail |
|-------|--------|
| **Impact** | `IncidentService` exists with cache invalidation, business event tracking, eager loading (selectinload), and pagination — but incident routes do raw SQLAlchemy queries directly. Duplicated logic, no cache invalidation on writes, possible N+1 queries, harder to test. Same issue with complaints. |
| **Evidence** | `src/api/routes/incidents.py` L109-122: raw `select(Incident).where(...)` instead of `IncidentService.get()`. `src/domain/services/incident_service.py` has full CRUD with `selectinload(Incident.actions)` and `invalidate_tenant_cache()`. |
| **Effort** | **M** (refactor 2 route files to call existing services) |
| **Fix** | Refactor `incidents.py` and `complaints.py` to instantiate `IncidentService(db)` / `ComplaintService(db)` and call service methods instead of raw queries. Map domain exceptions to HTTP responses. Create `ComplaintService` if it doesn't exist. |
| **Dimensions** | D09 Architecture (+0.3), D21 Code Quality (+0.3), D04 Performance (+0.2) |
| **Tests** | Existing integration tests should continue to pass; add service-level unit tests |
| **Rollback** | Revert to direct queries |

### 8. Standardize Pagination Response Shape Across All Endpoints

| Field | Detail |
|-------|--------|
| **Impact** | Frontend `PaginatedResponse<T>` expects `{items, total, page, page_size, pages}`. But backend returns `total_pages` (not `pages`) from investigation routes, and some endpoints like `list_assessments` return unbounded lists with no pagination at all. |
| **Evidence** | `src/api/routes/incidents.py` L305-313: returns `total_pages` key. `frontend/src/api/client.ts` L482-488: `PaginatedResponse` interface uses `pages`. `src/api/routes/risks.py` L449-458: `list_assessments` returns a raw list with `limit(100)`, no pagination. |
| **Effort** | **M** |
| **Fix** | Define a shared `PaginatedResponse[T]` Pydantic schema in `src/api/schemas/common.py` with `items`, `total`, `page`, `page_size`, `pages`. Use it as `response_model` for ALL list endpoints. Rename `total_pages` → `pages` everywhere. Add pagination to `list_assessments`. |
| **Dimensions** | D10 API Quality (+0.4), D02 UX Quality (+0.2) |
| **Tests** | Contract test: all list endpoints return identical pagination shape |
| **Rollback** | Revert schema, keep existing shapes as aliases |

### 9. Add Composite Database Indexes for Common Query Patterns

| Field | Detail |
|-------|--------|
| **Impact** | Individual indexes exist on `tenant_id`, `status`, `created_at` — but queries always filter by `tenant_id` AND `status` or `tenant_id` ORDER BY `created_at`. Without composite indexes, PostgreSQL scans more rows than necessary, especially as data grows. |
| **Evidence** | `src/domain/models/incident.py` L67: `tenant_id` index. L77: `status` index. No composite. Same in `risk.py`, `complaint.py`, `audit.py`. List queries filter `WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC`. |
| **Effort** | **S** (Alembic migration + `__table_args__` on models) |
| **Fix** | Add `__table_args__` with composite indexes: `Index('ix_incidents_tenant_status', 'tenant_id', 'status')`, `Index('ix_incidents_tenant_created', 'tenant_id', 'created_at')` to Incident, Complaint, Risk, AuditRun models. Create Alembic migration. |
| **Dimensions** | D04 Performance (+0.3), D11 Data Model (+0.2) |
| **Tests** | Query plan test: `EXPLAIN` shows index scan, not sequential scan |
| **Rollback** | Revert migration (drop indexes) |

### 10. Add Request Logging Middleware

| Field | Detail |
|-------|--------|
| **Impact** | No structured request/response logging. When investigating production issues, there's no log of which endpoints were called, by whom, with what response codes and latencies. The `request_id` is generated but not logged in a request log entry. |
| **Evidence** | `src/main.py` middleware chain: `RequestStateMiddleware` sets `request_id` but doesn't log it. No access log middleware. JSON logging is configured (`pythonjsonlogger`) but only captures application-level logs, not request flow. |
| **Effort** | **S** (add middleware that logs method, path, status, duration, request_id) |
| **Fix** | Add a `RequestLoggingMiddleware` that logs: `method`, `path`, `status_code`, `duration_ms`, `request_id`, `user_id` (if available), `content_length`. Skip logging for `/health*`, `/docs`, `/redoc`. Avoid logging request bodies (PII risk). |
| **Dimensions** | D13 Observability (+0.3), D32 Supportability (+0.3) |
| **Tests** | Integration test: make request → verify structured log entry exists with correct fields |
| **Rollback** | Remove middleware |

---

## Tier 3 — UI/UX Focus (Items 11–15)

### 11. Wire Global Toast to API Error Interceptor

| Field | Detail |
|-------|--------|
| **Impact** | The global toast system (`ToastContext.tsx`) exists but isn't connected to the API interceptor. Pages individually manage error state with `useState` and `getApiErrorMessage()`. Some pages use `alert()` for errors (9 instances found). This creates inconsistent error UX. |
| **Evidence** | `frontend/src/pages/ComplaintDetail.tsx` L232: `alert(\`Failed to create action: ${getApiErrorMessage(err)}\`)`. `IncidentDetail.tsx` L235: same pattern. `MobileAuditExecution.tsx` L315,436,452: `alert()` for device permission errors. `RTADetail.tsx` L232: `alert()`. `WorkflowCenter.tsx` L227: `alert()`. Meanwhile `ToastContext.tsx` exports a standalone `toast` API designed for exactly this use case. |
| **Effort** | **M** |
| **Fix** | Import `toast` from `ToastContext.tsx` in `client.ts` interceptor. In the response error handler, call `toast.error(classifiedMessage)` for 403, 422, 429, 500 errors (NOT 401, which redirects). Then replace all `alert()` calls in pages with `toast.error()` / `toast.warning()`. |
| **Dimensions** | D02 UX Quality (+0.3), D14 Error Handling (+0.2) |
| **Tests** | E2E test: trigger error → verify toast appears (not alert); unit test: mock 500 → toast.error called |
| **Rollback** | Remove toast calls from interceptor; revert alert→toast changes |

### 12. Replace `alert()` with Toast in All Pages

| Field | Detail |
|-------|--------|
| **Impact** | 9 `alert()` calls across pages create jarring, unstyled, browser-native dialogs that block the UI thread. Modern apps use non-blocking toast/snackbar notifications. |
| **Evidence** | Files: `ComplaintDetail.tsx` L232, `IncidentDetail.tsx` L235, `RTADetail.tsx` L232, `MobileAuditExecution.tsx` L315/436/452, `ReportGenerator.tsx` L167, `WorkflowCenter.tsx` L227, `PortalRTAForm.tsx` L263. |
| **Effort** | **S** (replace 9 instances) |
| **Fix** | Import `toast` from `ToastContext.tsx`. Replace `alert(msg)` with `toast.error(msg)` for errors or `toast.success(msg)` for confirmations. For device permission errors, use `toast.warning(msg)`. |
| **Dimensions** | D02 UX Quality (+0.2), D14 Error Handling (+0.1) |
| **Tests** | Verify no `alert(` calls remain in `frontend/src/pages/` (grep check) |
| **Rollback** | Revert to `alert()` |

### 13. Add Breadcrumb Navigation to Detail Pages

| Field | Detail |
|-------|--------|
| **Impact** | No breadcrumb component exists anywhere in the frontend. Users on detail pages (e.g., `/incidents/42`) have no visual path indicator and must use the browser back button or sidebar to navigate. This violates WCAG 2.1 SC 2.4.8 (Location) and hurts UX. |
| **Evidence** | `grep -rn breadcrumb frontend/src/` returns zero results. 71+ pages, many with nested detail views. |
| **Effort** | **M** |
| **Fix** | Create `frontend/src/components/ui/Breadcrumb.tsx` using Radix UI or a simple component. Add `useBreadcrumbs()` hook that derives crumbs from `react-router-dom` `useLocation()`. Integrate into `Layout.tsx` or individual detail pages. Initial rollout: Dashboard → Module List → Detail. |
| **Dimensions** | D02 UX Quality (+0.3), D03 Accessibility (+0.2) |
| **Tests** | a11y test: breadcrumb has `nav` element with `aria-label="Breadcrumb"` |
| **Rollback** | Remove breadcrumb component |

### 14. Add Empty States to List Pages

| Field | Detail |
|-------|--------|
| **Impact** | Some list pages show empty tables when no data exists. Incidents page has empty states (`incidents.empty.title`), but not all modules follow this pattern. Empty states should guide users on what to do next. |
| **Evidence** | `frontend/src/pages/Incidents.tsx` L202-203: has i18n empty state. Need to verify coverage across all list pages (complaints, risks, audits, policies, RTAs, actions, etc.). |
| **Effort** | **S-M** |
| **Fix** | Create a reusable `EmptyState` component: icon, title, description, optional CTA button. Apply to all list pages: Complaints, Risks, Policies, RTAs, Actions, AuditRuns, Standards, Documents, Notifications. Use i18n keys for text. |
| **Dimensions** | D02 UX Quality (+0.2), D01 Product Clarity (+0.1) |
| **Tests** | Visual test: render list with empty data → EmptyState component visible |
| **Rollback** | Revert to empty table |

### 15. Add Skeleton Loading to Key List Pages

| Field | Detail |
|-------|--------|
| **Impact** | Dashboard has `CardSkeleton` loading states (added in Week-1), but other list pages (Incidents, Complaints, Risks, Audits, Policies) use a simple spinner or nothing during load. Skeleton loading provides better perceived performance and prevents layout shift. |
| **Evidence** | Dashboard uses `CardSkeleton` from Week-1 uplift. Other pages: `Incidents.tsx` uses `Loader2` spinner. `Complaints.tsx`, `Risks.tsx` similar pattern. |
| **Effort** | **M** |
| **Fix** | Create a `TableSkeleton` component (animated rows with placeholder cells). Apply to the 6 most-used list pages: Incidents, Complaints, Risks, Audits, Policies, RTAs. Replace `Loader2` spinner with `TableSkeleton` in loading state. |
| **Dimensions** | D04 Performance (perceived) (+0.2), D02 UX Quality (+0.2) |
| **Tests** | Visual test: loading state renders skeleton rows; E2E: loading → content transition is smooth |
| **Rollback** | Revert to spinner |

---

## Implementation Schedule

### Week 1 — Low Effort / High Value (Items 1–5)

| # | Item | Effort | Files | WCS Impact |
|---|------|--------|-------|-----------|
| 1 | Fix risk JSON column bug | S | `src/api/routes/risks.py` | D24 +0.3 |
| 2 | Add GZip middleware | S | `src/main.py` | D04 +0.3 |
| 3 | Standardize error responses | S | All route files | D10 +0.3 |
| 4 | Mount health router / readyz Redis | S | `src/main.py`, `src/api/__init__.py` | D05 +0.3 |
| 5 | Add 429 handling to interceptor | S | `frontend/src/api/client.ts` | D14 +0.2 |

### Week 2 — Critical Workflows (Items 6–10)

| # | Item | Effort | Files | WCS Impact |
|---|------|--------|-------|-----------|
| 6 | Status transition validation | M | Models + route handlers | D24 +0.3 |
| 7 | Wire routes through service layer | M | `incidents.py`, `complaints.py` | D09 +0.3 |
| 8 | Standardize pagination shape | M | All list endpoints + schema | D10 +0.4 |
| 9 | Composite database indexes | S | Models + Alembic migration | D04 +0.3 |
| 10 | Request logging middleware | S | `src/main.py` or new middleware file | D13 +0.3 |

### Week 3 — UI/UX Focus (Items 11–15)

| # | Item | Effort | Files | WCS Impact |
|---|------|--------|-------|-----------|
| 11 | Wire toast to API interceptor | M | `client.ts` | D02 +0.3 |
| 12 | Replace alert() with toast | S | 6 page files | D02 +0.2 |
| 13 | Add breadcrumb navigation | M | New component + Layout | D02 +0.3 |
| 14 | Add empty states to list pages | S-M | 8 list page files | D02 +0.2 |
| 15 | Skeleton loading on list pages | M | 6 list page files + new component | D04 +0.2 |

---

## Expected Aggregate Impact

| Dimension | Current WCS | Expected After All 15 | Lift |
|-----------|-----------|----------------------|------|
| D02 UX Quality | 7.2 | 8.4 | +1.2 |
| D04 Performance | 5.4 | 6.5 | +1.1 |
| D05 Reliability | 8.0 | 8.6 | +0.6 |
| D09 Architecture | 8.0 | 8.6 | +0.6 |
| D10 API Quality | 8.0 | 8.9 | +0.9 |
| D11 Data Model | 8.0 | 8.4 | +0.4 |
| D13 Observability | 7.2 | 8.0 | +0.8 |
| D14 Error Handling | 8.0 | 8.5 | +0.5 |
| D21 Code Quality | 6.0 | 6.8 | +0.8 |
| D24 Data Integrity | 9.0 | 9.6 | +0.6 |
| D32 Supportability | 7.2 | 7.8 | +0.6 |
| **Average WCS** | **7.1** | **~7.6** | **+0.5** |

---

## Validation Checklist

After all 15 items are complete:

- [ ] Zero `alert()` calls in `frontend/src/pages/`
- [ ] All list endpoints return `{items, total, page, page_size, pages}` shape
- [ ] All 404/409/403 errors use `api_error()` envelope
- [ ] `/readyz` checks DB + Redis
- [ ] Status transitions validated server-side for incidents, complaints, risks, audit runs
- [ ] Composite indexes on `(tenant_id, status)` and `(tenant_id, created_at)` for 4 core models
- [ ] Risk update correctly writes to `_json_legacy` columns
- [ ] GZip responses for payloads > 1KB
- [ ] Request logging captures method, path, status, duration, request_id
- [ ] Breadcrumb navigation on all detail pages
- [ ] Global toast shown on API errors (not local state or alert)
- [ ] Empty states on all list pages
- [ ] Skeleton loading on 6 key list pages
- [ ] 429 rate-limit errors show user-friendly message
- [ ] CI passes all existing tests
