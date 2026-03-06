# Comprehensive Action Plan — Quality Governance Platform

**Version:** 1.0 | **Date:** 2026-03-06 | **Status:** APPROVED FOR EXECUTION
**Audit Type:** Full-Sweep Pre-Launch Enterprise Audit
**Release Readiness:** GO-WITH-RESTRICTIONS (P0 blockers must be resolved first)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Round 1 — Critical Blockers (P0): Data Integrity & Broken Workflows](#round-1)
3. [Round 2 — Major Defects (P1): Security, CI Pipeline, Error Handling](#round-2)
4. [Round 3 — Hardening (P2): Reliability, Performance, Privacy, Schema](#round-3)
5. [Round 4 — Polish & Future-Proofing (P3): DX, Accessibility, Observability](#round-4)
6. [Master Findings Register](#master-findings-register)
7. [Release Gating Criteria](#release-gating)
8. [Rollback Protocol](#rollback-protocol)

---

## Executive Summary

This plan consolidates findings from **4 independent audit sweeps** across the full stack:

| Sweep | Scope | Findings |
|-------|-------|----------|
| **Sweep 1** | FE/BE alignment, API contracts, error handling | 40 issues |
| **Sweep 2** | DB migrations, model-schema mismatches, indexes | 6 issues |
| **Sweep 3** | FE routing, auth protection, service worker, 404 handling | 12 issues |
| **Sweep 4** | Backend services, Celery tasks, concurrency, idempotency | 11 issues |

**Total unique findings: 69**

| Severity | Count | Description |
|----------|-------|-------------|
| **P0** | 8 | Release blockers — data corruption, broken core workflows |
| **P1** | 16 | Major defects — security, CI, user-facing errors |
| **P2** | 24 | Hardening — reliability, performance, privacy |
| **P3** | 21 | Polish — DX, accessibility, observability |

---

<a name="round-1"></a>
## ROUND 1 — Critical Blockers (P0)
### Theme: "Can the system actually write and read data correctly?"

**Goal:** Fix all data integrity and core workflow blockers. After Round 1, users can create, read, update incidents, audits, risks, complaints, investigations, and comments without errors.

**Estimated effort:** 1 day | **Risk:** LOW (small, isolated changes)

---

### R1-01: Fix CHECK Constraints to Accept Lowercase Enum Values

**Findings:** F-001, F-002, F-003, F-004, F-032

**Root Cause:**
- Migration `20260221_add_data_integrity_constraints.py` added CHECK constraints requiring UPPERCASE values: `status IN ('REPORTED', 'UNDER_INVESTIGATION', ...)`
- Migration `20260305_normalize_enum_case.py` lowercased all existing data
- `CaseInsensitiveEnum` TypeDecorator writes lowercase values
- Result: **Any new record insert fails** with `CheckViolationError`

**Evidence:**
- `alembic/versions/20260221_add_data_integrity_constraints.py:51-63` — UPPERCASE CHECK constraints
- `src/domain/models/base.py` CaseInsensitiveEnum — writes lowercase
- CI UAT log: `asyncpg.exceptions.CheckViolationError: ck_incidents_status`

**Change:**
```
New Alembic migration: 20260306_fix_check_constraints_lowercase.py

For each constraint (ck_incidents_status, ck_risks_status, ck_audits_status, ck_complaints_status):
  1. DROP CONSTRAINT IF EXISTS
  2. ADD CONSTRAINT with lowercase values

Example:
  DROP: ck_incidents_status
  ADD:  ck_incidents_status CHECK (status IN ('reported','under_investigation','pending_actions','actions_in_progress','pending_review','closed'))
```

**Files to change:**
- `alembic/versions/20260306_fix_check_constraints_lowercase.py` (NEW)

**Tests:**
- Re-run `tests/uat/test_stage1_basic_workflows.py` — must pass
- New unit test: insert lowercase status values into each table

**Rollback:** `alembic downgrade -1`

**Definition of Done:**
- [ ] Migration runs without error on staging
- [ ] Can create incident via portal with status='reported'
- [ ] Can create audit run with status='planned'
- [ ] Can create risk with status='open'
- [ ] Can create complaint with status='received'
- [ ] UAT tests pass in CI

---

### R1-02: Fix Investigation Comment Field Name Mismatch

**Finding:** F-005

**Root Cause:**
- Frontend sends: `POST { body: "comment text" }`
- Backend expects: `content: str` as a query/form parameter (not JSON body)

**Evidence:**
- `frontend/src/api/client.ts:1642-1644` — sends `{ body }`
- `src/api/routes/investigations.py:782-790` — expects `content: str`

**Change (Backend — preferred, avoids FE redeploy):**
```python
# investigations.py — change add_comment to accept JSON body
class AddCommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    section_id: Optional[str] = None
    field_id: Optional[str] = None
    parent_comment_id: Optional[int] = None

@router.post("/{investigation_id}/comments", status_code=201)
async def add_comment(
    investigation_id: int,
    payload: AddCommentRequest,
    db: DbSession,
    current_user: CurrentUser,
):
```

AND update frontend to send `content` instead of `body`:
```typescript
// client.ts:1642
addComment: (id: number, body: string) =>
    api.post(`/api/v1/investigations/${id}/comments`, { content: body }),
```

**Files to change:**
- `src/api/routes/investigations.py` — add Pydantic model, update endpoint
- `frontend/src/api/client.ts` — change `{ body }` to `{ content: body }`

**Tests:**
- `tests/integration/test_investigation_timeline_comments_packs.py` — verify comment creation
- New test: POST with `{ content: "test" }` returns 201

**Rollback:** Revert commit

**Definition of Done:**
- [ ] Can post comment from Investigation detail page
- [ ] Comment appears in timeline
- [ ] Integration test passes

---

### R1-03: Fix Risk Register Response Shape Mismatch

**Finding:** F-006

**Root Cause:**
- Backend returns: `{ "total": N, "risks": [...] }`
- Frontend reads: `response.data?.items ?? []`
- Result: Risk list is always empty

**Evidence:**
- `src/api/routes/risk_register.py:155-176` — returns `"risks"` key
- `frontend/src/pages/RiskRegister.tsx:112` — reads `.items`

**Change (Backend — align with standard pagination envelope):**
```python
# risk_register.py:155
return {
    "items": [  # Changed from "risks" to "items"
        { ... }
        for r in risks
    ],
    "total": total,
    "page": page,
    "page_size": limit,
}
```

**Files to change:**
- `src/api/routes/risk_register.py` — change `"risks"` to `"items"`

**Tests:**
- New integration test: `GET /risk-register/` response has `items` key
- Verify `RiskRegister.tsx` renders risks

**Rollback:** Revert commit

**Definition of Done:**
- [ ] Risk register page shows risks
- [ ] Response schema matches standard pagination envelope

---

### R1-04: Add Missing Investigation Detail Route

**Finding:** F-041 (NEW from Sweep 3)

**Root Cause:**
- `InvestigationDetail.tsx` exists but no route `investigations/:id` in `App.tsx`
- Multiple pages navigate to `/investigations/${id}` (Incidents, Complaints, RTAs)
- Users clicking through get a blank page

**Evidence:**
- `frontend/src/App.tsx` — no `path="investigations/:id"` route
- `frontend/src/pages/Investigations.tsx:220` — `navigate(/investigations/${id})`
- `frontend/src/pages/InvestigationDetail.tsx` — exists, fully implemented

**Change:**
```tsx
// App.tsx — add inside investigation routes
<Route path="investigations/:id" element={<InvestigationDetail />} />
```

**Files to change:**
- `frontend/src/App.tsx` — add route + lazy import

**Tests:**
- Navigate from incident detail to investigation → page loads

**Rollback:** Revert commit

**Definition of Done:**
- [ ] `/investigations/123` renders InvestigationDetail
- [ ] Navigation from Incidents/Complaints/RTAs works

---

### R1-05: Fix Risk Schema Validation Aliases

**Finding:** F-042 (NEW from Sweep 2)

**Root Cause:**
- Model uses `clause_ids_json_legacy`, `control_ids_json_legacy`, etc.
- Schema expects `clause_ids`, `control_ids`, etc. — without `validation_alias`
- Result: These fields always return `None` in API responses

**Evidence:**
- `src/domain/models/risk.py` — `clause_ids_json_legacy`, `control_ids_json_legacy`, `linked_audit_ids_json_legacy`, `linked_incident_ids_json_legacy`, `linked_policy_ids_json`
- `src/api/schemas/risk.py` — no `validation_alias` for these fields

**Change:**
```python
# risk.py schema
clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json_legacy")
control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json_legacy")
linked_audit_ids: Optional[List[int]] = Field(None, validation_alias="linked_audit_ids_json_legacy")
linked_incident_ids: Optional[List[int]] = Field(None, validation_alias="linked_incident_ids_json_legacy")
linked_policy_ids: Optional[List[int]] = Field(None, validation_alias="linked_policy_ids_json")
```

**Files to change:**
- `src/api/schemas/risk.py`

**Tests:**
- `tests/unit/test_risk_schemas.py` — assert fields resolve from model attrs

**Rollback:** Revert commit

**Definition of Done:**
- [ ] Risk API responses include clause_ids, control_ids, linked IDs when present

---

### R1-06: Register Idempotency Middleware

**Finding:** F-043 (NEW from Sweep 4)

**Root Cause:**
- `IdempotencyMiddleware` exists in `src/api/middleware/idempotency.py`
- But it is **never registered** in `main.py`
- CORS `allow_headers` doesn't include `Idempotency-Key`

**Evidence:**
- `src/api/middleware/idempotency.py` — full implementation
- `src/main.py:221-259` — middleware stack does not include `IdempotencyMiddleware`
- `src/main.py:243-250` — `allow_headers` missing `Idempotency-Key`

**Change:**
```python
# main.py — add to middleware stack
from src.api.middleware.idempotency import IdempotencyMiddleware
app.add_middleware(IdempotencyMiddleware)

# CORS allow_headers — add "Idempotency-Key"
```

**Files to change:**
- `src/main.py`

**Tests:**
- Send duplicate POST with same `Idempotency-Key` → 409
- Send POST without key → normal processing

**Rollback:** Remove middleware registration

**Definition of Done:**
- [ ] Idempotency-Key header accepted
- [ ] Duplicate requests return 409
- [ ] Normal requests unaffected

---

### R1-07: Fix FK Index Migration (risk_mitigations → risk_controls)

**Finding:** F-044 (NEW from Sweep 2)

**Root Cause:**
- Migration `20260221_add_foreign_key_indexes.py:35-37` references `risk_mitigations`
- Actual table is `risk_controls` (`src/domain/models/risk.py:106`)
- Indexes never created → slow JOINs on risk_controls

**Evidence:**
- `alembic/versions/20260221_add_foreign_key_indexes.py:35-37` — `risk_mitigations`
- `src/domain/models/risk.py:106` — `__tablename__ = "risk_controls"`

**Change:**
```
New migration: 20260306_fix_risk_controls_indexes.py
  CREATE INDEX IF NOT EXISTS ix_risk_controls_risk_id ON risk_controls(risk_id);
  CREATE INDEX IF NOT EXISTS ix_risk_controls_owner_id ON risk_controls(owner_id);
```

**Files to change:**
- `alembic/versions/20260306_fix_risk_controls_indexes.py` (NEW)

**Rollback:** `alembic downgrade -1`

**Definition of Done:**
- [ ] Indexes exist on risk_controls.risk_id and risk_controls.owner_id

---

### R1-08: Add 404 Catch-All Route

**Finding:** F-045 (NEW from Sweep 3)

**Root Cause:**
- No `path="*"` route in `App.tsx`
- Unmatched URLs render blank page

**Change:**
```tsx
// App.tsx — add at end of route tree
<Route path="*" element={<NotFound />} />
```

Create `NotFound.tsx` with navigation back to dashboard.

**Files to change:**
- `frontend/src/App.tsx`
- `frontend/src/pages/NotFound.tsx` (NEW)

**Rollback:** Revert commit

**Definition of Done:**
- [ ] `/nonexistent-page` shows 404 page with link to dashboard

---

## ROUND 1 SUMMARY

| ID | Action | Files | Effort | Risk |
|----|--------|-------|--------|------|
| R1-01 | Fix CHECK constraints to lowercase | 1 new migration | S | Low |
| R1-02 | Fix investigation comment field name | 2 files (BE + FE) | S | Low |
| R1-03 | Fix risk register response shape | 1 file (BE) | S | Low |
| R1-04 | Add investigation detail route | 1 file (FE) | S | Low |
| R1-05 | Fix risk schema validation aliases | 1 file (BE) | S | Low |
| R1-06 | Register idempotency middleware | 1 file (BE) | S | Med |
| R1-07 | Fix FK index migration table name | 1 new migration | S | Low |
| R1-08 | Add 404 catch-all route | 2 files (FE) | S | Low |

**Total Round 1: 8 items, all Small effort**

---

<a name="round-2"></a>
## ROUND 2 — Major Defects (P1)
### Theme: "Can users trust the system to tell them what went wrong?"

**Goal:** Fix security gaps, CI pipeline, and ensure all API errors are visible to users. After Round 2, the CI pipeline is green, no unauthenticated endpoints exist, and users see meaningful error messages for every failed operation.

**Estimated effort:** 2-3 days | **Risk:** LOW-MEDIUM

---

### R2-01: Add Auth to Copilot Session Endpoints

**Finding:** F-008

**Root Cause:** `get_session` and `close_session` endpoints lack `CurrentUser` dependency.

**Evidence:** `src/api/routes/copilot.py:126-148`

**Change:**
```python
# Add current_user: CurrentUser to both endpoints
@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: DbSession, current_user: CurrentUser):
    ...

@router.delete("/sessions/{session_id}")
async def close_session(session_id: str, db: DbSession, current_user: CurrentUser):
    ...
```

**Files:** `src/api/routes/copilot.py`
**Tests:** Add to `tests/integration/test_auth_boundaries.py`
**Rollback:** Revert commit
**DoD:** 401 returned without token; existing functionality preserved with token

---

### R2-02: Fix CI Code Quality — Black Formatting

**Finding:** F-009

**Root Cause:** 9 files not Black-formatted after CaseInsensitiveEnum changes.

**Evidence:** CI run `22738822787` — `9 files would be reformatted`

**Change:**
```bash
black src/api/routes/audits.py \
      src/domain/models/assessment.py \
      src/domain/models/asset.py \
      src/domain/models/document.py \
      src/domain/models/incident.py \
      src/domain/models/loler.py \
      src/domain/models/investigation.py \
      src/domain/models/policy.py \
      src/domain/models/rta.py
```

**Files:** 9 files listed above
**Tests:** CI Code Quality gate
**Rollback:** Revert commit
**DoD:** CI Code Quality job passes

---

### R2-03: Fix FE 422 Error Envelope Parsing

**Finding:** F-007

**Root Cause:**
- Backend returns `{ error: { code, message, details: { errors: [...] } } }`
- Frontend reads `data.detail` or `data.message` for 422s
- Result: Generic "Validation error" instead of field-level messages

**Evidence:**
- `frontend/src/api/client.ts:396-399` — reads `data.detail`
- `src/api/middleware/error_handler.py:117-125` — returns `{ error: {...} }`

**Change:**
```typescript
// client.ts error interceptor — update 422 handling
if (status === 422) {
  const errorPayload = data?.error || data;
  const fieldErrors = errorPayload?.details?.errors;
  if (fieldErrors && Array.isArray(fieldErrors)) {
    classifiedMessage = fieldErrors.map(e => `${e.field}: ${e.message}`).join('; ');
  } else {
    classifiedMessage = errorPayload?.message || data?.detail || 'Validation error';
  }
}
```

**Files:** `frontend/src/api/client.ts`
**Tests:** `tests/unit/test_api_client_contracts.py` — mock 422 response, assert parsed message
**Rollback:** Revert commit
**DoD:** Form validation errors show field-specific messages

---

### R2-04: Surface API Errors in All Create Forms

**Findings:** F-012, F-013, F-014, F-015

**Root Cause:** `catch` blocks in Incidents, Complaints, RTAs, Risks only `console.error`; no user-facing feedback.

**Evidence:**
- `Incidents.tsx:77-78` — `console.error('Failed to create:', error)`
- `Complaints.tsx:85-88` — same
- `RTAs.tsx:125-127` — same
- `Risks.tsx:76-77` — same

**Change (for each page):**
```typescript
// Add error state
const [createError, setCreateError] = useState<string | null>(null);

// In catch block
catch (error) {
  console.error('Failed to create:', error);
  setCreateError(getApiErrorMessage(error));
}

// In JSX — add error banner above form
{createError && (
  <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
    {createError}
    <button onClick={() => setCreateError(null)} className="ml-2 text-red-600">×</button>
  </div>
)}
```

**Files:** `Incidents.tsx`, `Complaints.tsx`, `RTAs.tsx`, `Risks.tsx`
**Tests:** Vitest: mock API error → assert error banner renders
**Rollback:** Revert commit
**DoD:** All 4 create forms show error messages on API failure

---

### R2-05: Fix Swallowed Errors in List/Workforce Pages

**Findings:** F-016, F-017

**Root Cause:** `.catch(() => {})` and `console.error`-only patterns across 10+ pages.

**Evidence:**
- `Training.tsx:47,56,59` — `.catch(() => {})`
- `Assessments.tsx:51,60,69` — `.catch(() => {})`
- `Calendar.tsx:37` — `.catch(() => {})`
- `EngineerProfile.tsx:30` — `.catch(() => {})`
- `Standards.tsx:70-71` — `console.error` only
- `Documents.tsx:129-130` — `console.error` only
- `Policies.tsx:49-50` — `console.error` only

**Change:**
Add error state + error display for each page. Replace `.catch(() => {})` with `.catch(err => setError(getApiErrorMessage(err)))`.

**Files:** 10 page files
**Tests:** Vitest: mock API failure → assert error state set
**Rollback:** Revert commit
**DoD:** No silent error swallowing on any page

---

### R2-06: Fix AdminDashboard Dead Links

**Finding:** F-046 (Sweep 3)

**Root Cause:** Admin quick action links point to non-existent routes.

**Evidence:**
- `AdminDashboard.tsx:63` — `/admin/users` (should be `/users`)
- `AdminDashboard.tsx:70` — `/admin/lookups` (no route)
- `AdminDashboard.tsx:76` — `/admin/notifications` (no route)

**Change:** Fix hrefs to existing routes or remove links to non-existent pages.

**Files:** `frontend/src/pages/admin/AdminDashboard.tsx`
**Rollback:** Revert commit
**DoD:** All admin quick action links navigate to valid pages

---

### R2-07: Fix Service Worker Cache Version Replacement

**Finding:** F-047 (Sweep 3)

**Root Cause:**
- `sw.js:9` uses `CACHE_VERSION = '__SW_VERSION__'`
- CI sed pattern doesn't match this format → cache never invalidated
- Users may get stale frontend assets

**Evidence:** `frontend/public/sw.js:9`

**Change:** Fix the sed pattern in CI to match `__SW_VERSION__`, OR change SW to use a different cache busting strategy (e.g., build hash from `meta/version`).

**Files:** `frontend/public/sw.js`, `.github/workflows/azure-static-web-apps-*.yml`
**Tests:** Verify `sw.js` contains correct version string after build
**Rollback:** Revert commit
**DoD:** Cache version updates on each deploy

---

### R2-08: Fix Service Worker Background Sync URL

**Finding:** F-048 (Sweep 3)

**Root Cause:**
- `sw.js:345` uses `fetch('/api/v1/portal/report')` with relative URL
- Frontend and API are on different origins (SWA vs Azure App Service)
- Background sync requests hit the wrong origin

**Change:** Use absolute API URL from SW config or pass API URL to SW during registration.

**Files:** `frontend/public/sw.js`
**Rollback:** Revert commit
**DoD:** Background sync requests hit the correct API origin

---

### R2-09: Add FE Role-Based Route Protection

**Finding:** F-049 (Sweep 3)

**Root Cause:**
- All authenticated users can access `/admin/*`, `/users`, `/audit-trail`
- No role checking in frontend routing

**Change:**
```tsx
// Create ProtectedRoute wrapper
const ProtectedRoute = ({ requiredRole, children }) => {
  const user = useAuth();
  if (!user.roles.includes(requiredRole)) return <Navigate to="/dashboard" />;
  return children;
};

// Wrap admin routes
<Route path="admin" element={<ProtectedRoute requiredRole="admin"><AdminDashboard /></ProtectedRoute>} />
```

**Files:** `frontend/src/App.tsx`, `frontend/src/components/ProtectedRoute.tsx` (NEW)
**Tests:** Vitest: non-admin user redirected from admin routes
**Rollback:** Revert commit
**DoD:** Admin pages only accessible to admin-role users

---

### R2-10: Implement Real Email Sending in Celery Task

**Finding:** F-050 (Sweep 4)

**Root Cause:**
- `send_email` Celery task is a **stub** — logs and returns `{"status": "sent"}` without calling `EmailService`
- No emails are actually sent by the system

**Evidence:** `src/infrastructure/tasks/email_tasks.py:10-24`

**Change:** Wire `send_email` task to `EmailService.send_email()`.

**Files:** `src/infrastructure/tasks/email_tasks.py`
**Tests:** Unit test with mocked SMTP
**Rollback:** Revert commit
**DoD:** Emails are actually sent via SMTP when task is triggered

---

## ROUND 2 SUMMARY

| ID | Action | Files | Effort | Risk |
|----|--------|-------|--------|------|
| R2-01 | Auth on copilot endpoints | 1 | S | Low |
| R2-02 | Black format 9 files | 9 | S | Low |
| R2-03 | Fix 422 error envelope parsing | 1 | S | Low |
| R2-04 | Surface create errors in 4 forms | 4 | M | Low |
| R2-05 | Fix swallowed errors in 10 pages | 10 | M | Low |
| R2-06 | Fix admin dead links | 1 | S | Low |
| R2-07 | Fix SW cache version | 2 | S | Low |
| R2-08 | Fix SW background sync URL | 1 | S | Low |
| R2-09 | Add role-based route protection | 2 | M | Med |
| R2-10 | Wire email task to EmailService | 1 | M | Med |

**Total Round 2: 10 items**

---

<a name="round-3"></a>
## ROUND 3 — Hardening (P2)
### Theme: "Make it resilient, fast, and private"

**Goal:** Harden the system for production reliability. After Round 3, the system handles edge cases gracefully, protects PII, uses correct serialization, and performs well under load.

**Estimated effort:** 3-5 days | **Risk:** MEDIUM

---

### R3-01: Mask PII in Auth and Email Logs

**Findings:** F-018, F-019

**Change:**
```python
# auth.py:120 — mask email
logger.info("Created new user from Azure AD: %s***@%s", email[:3], email.split("@")[1] if "@" in email else "***")

# email_tasks.py:20 — mask recipient
logger.info("Sending email to %s...: %s", to[:3] + "***", subject[:20] + "...")
```

**Files:** `src/api/routes/auth.py`, `src/infrastructure/tasks/email_tasks.py`
**DoD:** No full email addresses in log output

---

### R3-02: Replace pickle with JSON in Redis Cache

**Finding:** F-020

**Change:** Replace `pickle.loads`/`pickle.dumps` with `json.loads`/`json.dumps` in `redis_cache.py`.

**Files:** `src/infrastructure/cache/redis_cache.py`
**Rollback:** Revert + flush Redis
**DoD:** Cache read/write works with JSON serialization

---

### R3-03: Add AbortController to Page useEffects

**Findings:** F-021, F-022, F-023

**Change:** Add AbortController with cleanup return to useEffect hooks in all pages that fetch data.

**Files:** `Incidents.tsx`, `Complaints.tsx`, `Dashboard.tsx`, `RTAs.tsx`, `WorkflowCenter.tsx`, `PortalTrack.tsx`, + workforce pages
**DoD:** No React state-update-on-unmounted-component warnings

---

### R3-04: Add Optimistic Locking to Audit Template PATCH

**Finding:** F-051 (Sweep 4)

**Root Cause:**
- `PATCH /audits/templates/{id}` has no version check
- Concurrent edits overwrite each other silently

**Change:** Add `version` parameter to PATCH; return 409 on mismatch.

**Files:** `src/api/routes/audits.py`, `frontend/src/pages/AuditTemplateBuilder.tsx`
**DoD:** Concurrent edits detected and rejected with user-facing message

---

### R3-05: Add Document Upload Size Limit and Storage

**Finding:** F-052 (Sweep 4)

**Root Cause:**
- `documents.py` has no size limit
- Azure Blob upload is a TODO stub

**Change:**
- Add `MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024` validation
- Wire upload to `AzureBlobStorageService`

**Files:** `src/api/routes/documents.py`, `src/infrastructure/storage.py`
**DoD:** Files upload to Azure Blob; oversized files rejected with 413

---

### R3-06: Add Missing FK Indexes for Documents and Investigations

**Finding:** F-053 (Sweep 2)

**Change:** New migration adding indexes for:
- `documents.linked_policy_id`, `documents.linked_standard_id`, `documents.created_by_id`
- `document_annotations.document_id`, `document_annotations.user_id`
- `document_versions.document_id`
- `investigation_comments.parent_comment_id`
- `investigation_revision_events.actor_id`

**Files:** New Alembic migration
**DoD:** Indexes exist on all FK columns

---

### R3-07: Fix AI Service Silent Exception Swallowing

**Finding:** F-054 (Sweep 4)

**Root Cause:** `ai_audit_service.py` has `except Exception: pass` — AI failures completely hidden.

**Change:** Log exceptions; return explicit fallback; do not `pass` silently.

**Files:** `src/domain/services/ai_audit_service.py`
**DoD:** AI failures logged with level ERROR; fallback templates returned

---

### R3-08: Fix Locust Performance Test Parameters

**Finding:** F-030

**Change:** Replace `per_page` with `page_size` in all Locust task definitions.

**Files:** `tests/performance/locustfile.py`
**DoD:** Locust tests hit correct query params

---

### R3-09: Fix apiBase.ts Localhost Environment Detection

**Finding:** F-055 (Sweep 3)

**Root Cause:** `apiUrl.includes('localhost')` returns `'staging'` instead of `'development'`.

**Change:** Return `'development'` when URL contains `localhost`.

**Files:** `frontend/src/config/apiBase.ts`
**DoD:** Local development correctly identified as 'development' environment

---

### R3-10: Remove Dead exceptions.py

**Findings:** F-029, F-036

**Change:** Delete `src/api/exceptions.py` (unused; different error envelope from `error_handler.py`).

**Files:** `src/api/exceptions.py` (DELETE)
**DoD:** No dead exception code

---

### R3-11: Wire Push Notification Task to Real Service

**Finding:** F-056 (Sweep 4)

**Root Cause:** `send_push_notification` Celery task is a stub.

**Change:** Implement Web Push delivery using `pywebpush` library (already in requirements).

**Files:** `src/infrastructure/tasks/notification_tasks.py`, `src/domain/services/notification_service.py`
**DoD:** Push notifications delivered to subscribed browsers

---

### R3-12: Add Retry Logic for External API Calls

**Finding:** F-028

**Change:** Add `tenacity` retry decorator to Azure Blob, AI service, and email service calls.

**Files:** `src/infrastructure/storage.py`, `src/domain/services/gemini_ai_service.py`, `src/domain/services/email_service.py`
**DoD:** Transient failures retried up to 3 times with exponential backoff

---

## ROUND 3 SUMMARY

| ID | Action | Files | Effort | Risk |
|----|--------|-------|--------|------|
| R3-01 | Mask PII in logs | 2 | S | Low |
| R3-02 | Replace pickle with JSON | 1 | S | Med |
| R3-03 | Add AbortController | 10+ | M | Low |
| R3-04 | Optimistic locking on templates | 2 | M | Med |
| R3-05 | Document upload size + storage | 2 | M | Med |
| R3-06 | Add missing FK indexes | 1 migration | S | Low |
| R3-07 | Fix AI silent exception | 1 | S | Low |
| R3-08 | Fix Locust params | 1 | S | Low |
| R3-09 | Fix apiBase localhost detection | 1 | S | Low |
| R3-10 | Remove dead exceptions.py | 1 (delete) | S | Low |
| R3-11 | Wire push notification task | 2 | M | Med |
| R3-12 | Add retry logic for externals | 3 | M | Med |

**Total Round 3: 12 items**

---

<a name="round-4"></a>
## ROUND 4 — Polish & Future-Proofing (P3)
### Theme: "Make it maintainable, accessible, and observable"

**Goal:** Improve developer experience, accessibility, and observability. After Round 4, the codebase is clean, accessible, observable, and set up for long-term success.

**Estimated effort:** 5-7 days | **Risk:** LOW

---

### R4-01: Increase Frontend Test Coverage to 15%+

**Finding:** F-027

**Change:** Add Vitest tests for all major page components. Target: 15% statement coverage minimum.

Priority test files to create:
1. `Incidents.test.tsx` — render, load, create, error states
2. `AuditTemplateLibrary.test.tsx` — render, filter, publish
3. `RiskRegister.test.tsx` — render, create
4. `Investigations.test.tsx` — render, navigate
5. `Complaints.test.tsx` — render, create

**Files:** 5+ new test files in `frontend/src/pages/__tests__/`
**DoD:** `vitest --coverage` reports ≥15% statements

---

### R4-02: Split Large Page Components

**Findings:** F-024, F-025, F-026

**Change:** Refactor components >800 lines into sub-components:

| File | Lines | Split into |
|------|-------|-----------|
| InvestigationDetail.tsx | 1,888 | InvestigationHeader, InvestigationTimeline, InvestigationComments, InvestigationActions |
| AuditTemplateBuilder.tsx | 1,467 | TemplateHeader, SectionEditor, QuestionEditor, PublishDialog |
| AuditExecution.tsx | 1,197 | ExecutionHeader, QuestionRenderer, FindingPanel, ProgressBar |

**Files:** 3 large files → 12+ smaller files
**DoD:** No page file exceeds 500 lines

---

### R4-03: Add Accessibility Labels and Keyboard Navigation

**Findings:** F-034, F-035

**Change:**
- Add `aria-label` to all icon-only buttons
- Add `role="button"` and `tabIndex={0}` to RTA table rows
- Add `aria-label` to search inputs

**Files:** `RTAs.tsx`, `AssessmentExecution.tsx`, `PortalDynamicForm.tsx`, `AuditTrail.tsx`
**DoD:** Playwright a11y audit passes on affected pages

---

### R4-04: Consolidate console.error to Error Tracker

**Finding:** F-033

**Change:** Replace all 58 `console.error` calls with `trackError()` from error tracking service. Add structured context (component, action, user intent).

**Files:** 20+ page files
**DoD:** No raw `console.error` calls in page components

---

### R4-05: Move FRONTEND_URL to Config Settings

**Finding:** F-039

**Change:**
```python
# config.py
frontend_url: str = "http://localhost:3000"  # Override via FRONTEND_URL env var

# auth.py:315 — use settings
frontend_url = settings.frontend_url
```

**Files:** `src/core/config.py`, `src/api/routes/auth.py`
**DoD:** No hardcoded production URL in code

---

### R4-06: Define Formal SLOs

**Finding:** F-037

**Change:** Create SLO definitions:
- API p95 latency: <500ms for read, <1000ms for write
- Error rate: <0.5% for 2xx endpoints
- Availability: >99.5%
- Database query p95: <200ms

**Files:** `docs/slo.yaml` (NEW)
**DoD:** SLO document reviewed and approved

---

### R4-07: Fix Rate Limiter JWT Verification

**Finding:** F-031

**Change:** Verify JWT signature when extracting user ID for rate limit keying, or use a different identifier (e.g., IP + hashed token prefix).

**Files:** `src/infrastructure/middleware/rate_limiter.py`
**DoD:** No unverified JWT decoding

---

### R4-08: Resolve All TODO/FIXME Comments

**Evidence:** 49 TODO/FIXME across 24 files in `src/` and `frontend/src/`

**Change:** For each TODO:
- Implement if actionable and safe
- Convert to GitHub issue if deferred
- Remove if resolved

**Files:** 24 files across backend and frontend
**DoD:** `grep -r "TODO\|FIXME" src/ frontend/src/` returns zero results

---

### R4-09: Replace Stub Placeholder Pages with Real Implementations or "Coming Soon"

**Finding:** F-057 (Sweep 3)

**Root Cause:**
- `AIIntelligence.tsx` — hardcoded empty data, setTimeout mock
- `AdminDashboard.tsx` — hardcoded zero stats
- `IMSDashboard.tsx` — setTimeout mock data

**Change:** Either implement real API integration or show explicit "Coming Soon" badges with disabled interactions.

**Files:** 3 page files
**DoD:** No pages silently pretend to work with mock data

---

### R4-10: Add Email Template Variable Safety

**Finding:** F-058 (Sweep 4)

**Root Cause:** `EmailService` uses `.format()` which will raise `KeyError` on missing variables.

**Change:** Use `str.format_map(defaultdict(str, vars))` or template engine with safe defaults.

**Files:** `src/domain/services/email_service.py`
**DoD:** Missing template variables produce empty string instead of crash

---

### R4-11: Add HTTPS Enforcement for Staging in Service Worker

**Finding:** F-059 (Sweep 3)

**Root Cause:** SW only enforces HTTPS for `azurewebsites.net`, not `azurecontainerapps.io` (staging).

**Change:** Add `azurecontainerapps.io` to HTTPS enforcement scope.

**Files:** `frontend/public/sw.js`
**DoD:** HTTPS enforced on all Azure domains

---

## ROUND 4 SUMMARY

| ID | Action | Files | Effort | Risk |
|----|--------|-------|--------|------|
| R4-01 | Increase FE test coverage to 15%+ | 5+ new | L | Low |
| R4-02 | Split large components | 12+ files | L | Low |
| R4-03 | Accessibility labels/keyboard | 4 | S | Low |
| R4-04 | Consolidate console.error | 20+ | M | Low |
| R4-05 | Move FRONTEND_URL to config | 2 | S | Low |
| R4-06 | Define formal SLOs | 1 new doc | S | Low |
| R4-07 | Fix rate limiter JWT verification | 1 | S | Low |
| R4-08 | Resolve TODO/FIXME comments | 24 | M | Low |
| R4-09 | Replace stub pages | 3 | M | Low |
| R4-10 | Email template safety | 1 | S | Low |
| R4-11 | SW HTTPS for staging | 1 | S | Low |

**Total Round 4: 11 items**

---

<a name="master-findings-register"></a>
## Master Findings Register

| ID | Type | Sev | Area | Round | Action | Status |
|----|------|-----|------|-------|--------|--------|
| F-001 | BUG | P0 | DB | R1-01 | Fix CHECK constraint (incidents) | PENDING |
| F-002 | BUG | P0 | DB | R1-01 | Fix CHECK constraint (risks) | PENDING |
| F-003 | BUG | P0 | DB | R1-01 | Fix CHECK constraint (audits) | PENDING |
| F-004 | BUG | P0 | DB | R1-01 | Fix CHECK constraint (complaints) | PENDING |
| F-005 | FE_BE_MISALIGNMENT | P0 | API | R1-02 | Fix investigation comment field | PENDING |
| F-006 | FE_BE_MISALIGNMENT | P0 | API | R1-03 | Fix risk register response shape | PENDING |
| F-007 | FE_BE_MISALIGNMENT | P1 | API | R2-03 | Fix 422 error envelope parsing | PENDING |
| F-008 | SECURITY | P1 | BE | R2-01 | Auth on copilot endpoints | PENDING |
| F-009 | WARNING | P1 | CI | R2-02 | Black format 9 files | PENDING |
| F-010 | ERROR | P1 | CI | R1-01 | UAT tests fail (CHECK constraint) | PENDING |
| F-011 | ERROR | P1 | CI | R1-01 | E2E tests fail | PENDING |
| F-012 | BROKEN_WORKFLOW | P1 | FE | R2-04 | Incident create error hidden | PENDING |
| F-013 | BROKEN_WORKFLOW | P1 | FE | R2-04 | Complaint create error hidden | PENDING |
| F-014 | BROKEN_WORKFLOW | P1 | FE | R2-04 | RTA create error hidden | PENDING |
| F-015 | BROKEN_WORKFLOW | P1 | FE | R2-04 | Risk create error hidden | PENDING |
| F-016 | BROKEN_WORKFLOW | P1 | FE | R2-05 | Standards/Docs/Policies errors swallowed | PENDING |
| F-017 | BROKEN_WORKFLOW | P1 | FE | R2-05 | Workforce pages swallow errors | PENDING |
| F-018 | PRIVACY | P2 | BE | R3-01 | PII in auth logs | PENDING |
| F-019 | PRIVACY | P2 | BE | R3-01 | PII in email logs | PENDING |
| F-020 | SECURITY | P2 | BE | R3-02 | Pickle in Redis cache | PENDING |
| F-021 | PERF | P2 | FE | R3-03 | Missing AbortController (Incidents) | PENDING |
| F-022 | PERF | P2 | FE | R3-03 | Missing AbortController (10+ pages) | PENDING |
| F-023 | PERF | P2 | FE | R3-03 | RTAs AbortController not wired | PENDING |
| F-024 | DX | P3 | FE | R4-02 | InvestigationDetail 1,888 lines | PENDING |
| F-025 | DX | P3 | FE | R4-02 | AuditTemplateBuilder 1,467 lines | PENDING |
| F-026 | DX | P3 | FE | R4-02 | 10+ files >500 lines | PENDING |
| F-027 | DX | P3 | FE | R4-01 | FE test coverage 3% | PENDING |
| F-028 | RELIABILITY | P2 | BE | R3-12 | No retry logic for externals | PENDING |
| F-029 | WARNING | P2 | BE | R3-10 | Dead exceptions.py | PENDING |
| F-030 | WARNING | P2 | QA | R3-08 | Locust wrong param names | PENDING |
| F-031 | SECURITY | P3 | BE | R4-07 | Rate limiter unverified JWT | PENDING |
| F-032 | RELIABILITY | P0 | DB | R1-01 | CHECK vs lowercase data | PENDING |
| F-033 | WARNING | P3 | FE | R4-04 | 58 console.error calls | PENDING |
| F-034 | WARNING | P3 | FE | R4-03 | Missing aria-labels | PENDING |
| F-035 | WARNING | P3 | FE | R4-03 | RTA table keyboard nav | PENDING |
| F-036 | DX | P3 | BE | R3-10 | exceptions.py unused | PENDING |
| F-037 | WARNING | P3 | OPS | R4-06 | No formal SLOs | PENDING |
| F-038 | PERF | P3 | FE | R4-02 | No React.memo on pages | PENDING |
| F-039 | DX | P3 | BE | R4-05 | FRONTEND_URL hardcoded | PENDING |
| F-040 | WARNING | P3 | FE | R4-08 | Login placeholder check | PENDING |
| F-041 | BROKEN_WORKFLOW | P0 | FE | R1-04 | Missing investigations/:id route | PENDING |
| F-042 | BUG | P0 | BE | R1-05 | Risk schema missing aliases | PENDING |
| F-043 | RELIABILITY | P1 | BE | R1-06 | Idempotency middleware not registered | PENDING |
| F-044 | PERF | P1 | DB | R1-07 | FK index wrong table name | PENDING |
| F-045 | BROKEN_WORKFLOW | P1 | FE | R1-08 | No 404 catch-all route | PENDING |
| F-046 | BROKEN_WORKFLOW | P1 | FE | R2-06 | Admin dead links | PENDING |
| F-047 | BUG | P1 | FE | R2-07 | SW cache version not replaced | PENDING |
| F-048 | BUG | P1 | FE | R2-08 | SW background sync wrong URL | PENDING |
| F-049 | SECURITY | P1 | FE | R2-09 | No role-based route protection | PENDING |
| F-050 | BUG | P1 | BE | R2-10 | Email task is a stub | PENDING |
| F-051 | RELIABILITY | P2 | BE | R3-04 | No optimistic locking on templates | PENDING |
| F-052 | BUG | P2 | BE | R3-05 | Document upload no size limit | PENDING |
| F-053 | PERF | P2 | DB | R3-06 | Missing FK indexes (docs/investigations) | PENDING |
| F-054 | RELIABILITY | P2 | BE | R3-07 | AI silent exception swallowing | PENDING |
| F-055 | BUG | P2 | FE | R3-09 | apiBase localhost → staging | PENDING |
| F-056 | BUG | P1 | BE | R3-11 | Push notification task is stub | PENDING |
| F-057 | DX | P3 | FE | R4-09 | Stub placeholder pages | PENDING |
| F-058 | RELIABILITY | P3 | BE | R4-10 | Email template KeyError risk | PENDING |
| F-059 | SECURITY | P3 | FE | R4-11 | SW no HTTPS for staging | PENDING |

---

<a name="release-gating"></a>
## Release Gating Criteria

| Gate | Criteria | Required For |
|------|----------|-------------|
| **Gate A** | Black, isort, flake8, ESLint, TypeScript strict — all pass | Every PR |
| **Gate B** | Unit tests pass, coverage ≥ thresholds | Every PR |
| **Gate C** | Integration tests pass | Every PR |
| **Gate D** | Staging smoke tests pass (5/5 + E2E lifecycle) | Every deploy |
| **Gate E** | UAT sign-off (all CUJs pass) | Production release |
| **Gate F** | Post-deploy verification (health, readiness, version, key endpoints) | Within 5 min of prod deploy |
| **Gate G** | No P0 findings open | Production release |
| **Gate H** | All P1 findings resolved or risk-accepted with sign-off | Production release |

---

<a name="rollback-protocol"></a>
## Rollback Protocol

### Backend (Azure App Service)
1. Identify failing commit via `/api/v1/meta/version`
2. Trigger `rollback-production.yml` with previous known-good image tag
3. If migration-related: `alembic downgrade -1` via ACI migration container
4. Verify `/healthz` and `/readyz` return OK
5. Verify key endpoint returns 200

### Frontend (Azure Static Web Apps)
1. Push revert commit to `main`
2. SWA CI/CD auto-deploys
3. Force-clear SW cache if needed via version bump

### Escalation
- P0 rollback: Engineering Lead + Product Owner notified within 15 min
- P1 rollback: Engineering Lead notified within 1 hour
- Incident report filed in `/docs/incidents/` within 24 hours

---

## Execution Order Summary

```
ROUND 1 (Day 1)     → Data integrity + core workflows
  R1-01 CHECK constraints
  R1-02 Comment field fix
  R1-03 Risk register shape
  R1-04 Investigation route
  R1-05 Risk schema aliases
  R1-06 Idempotency middleware
  R1-07 FK index fix
  R1-08 404 route
  ─── DEPLOY + VERIFY ───

ROUND 2 (Days 2-3)  → Security + CI + error handling
  R2-01 Copilot auth
  R2-02 Black formatting
  R2-03 422 error parsing
  R2-04 Create form errors
  R2-05 Swallowed errors
  R2-06 Admin dead links
  R2-07 SW cache version
  R2-08 SW sync URL
  R2-09 Role protection
  R2-10 Email task
  ─── DEPLOY + VERIFY ───

ROUND 3 (Days 4-6)  → Hardening
  R3-01 through R3-12
  ─── DEPLOY + VERIFY ───

ROUND 4 (Days 7-10) → Polish
  R4-01 through R4-11
  ─── DEPLOY + VERIFY ───

POST-LAUNCH         → Stability retest at 30/90/180 days
```
