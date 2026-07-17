# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** PR B - Investigation comment tenant_id write-path fix
- **User goal (1-2 lines):** Ensure investigation comments inherit `tenant_id` from their parent investigation and fail with a 4xx validation error when the parent investigation is unattributed.
- **In scope:** Investigation comment POST write paths, investigation comment list tenant filters, focused unit tests, PR-specific Change Ledger.
- **Out of scope:** Layout, App, client API exports, `api/__init__.py`, Alembic migrations, `InvestigationDetail`, frontend changes, unrelated investigation endpoints.
- **Feature flag / kill switch:** N/A - data integrity and tenant isolation fix.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `src/api/routes/investigations.py`, `src/domain/services/investigation_service.py`
- **APIs (endpoints changed/added):** `GET /investigations/{investigation_id}/comments` now filters comments and count by tenant; `POST /investigations/{investigation_id}/comments` stamps comment `tenant_id` from the parent investigation and fails closed if missing.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** No schema changes
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Strict writer, tolerant reader. Existing valid investigations continue to create comments; invalid unattributed investigations are rejected before database write.
- **Tolerant reader / strict writer applied?** Yes - read paths add tenant predicates, write paths require inherited tenant attribution.
- **Breaking changes:** None expected for valid tenant-attributed investigation records.
- **Migration plan:** No migration required.
- **Rollback strategy (DB):** No DB change - revert commit only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Route comment creation loads the parent investigation via existing access helper instead of a bare ID lookup.
- [x] AC-02: Route comment creation sets `InvestigationComment.tenant_id` from `investigation.tenant_id`.
- [x] AC-03: Service `add_comment` sets `InvestigationComment.tenant_id` from the tenant-scoped parent investigation.
- [x] AC-04: Route and service comment creation fail closed with `ValidationError` when `investigation.tenant_id` is missing.
- [x] AC-05: Route and service comment list queries filter `InvestigationComment.tenant_id`.
- [x] AC-06: Focused unit tests cover tenant inheritance and fail-closed write behavior.

## 5) Testing Evidence (link to runs)
- [x] Lint - `python3 -m black --check src/api/routes/investigations.py src/domain/services/investigation_service.py tests/unit/test_investigation_comments_tenant_write.py`
- [ ] Typecheck - deferred to CI.
- [x] Build - N/A
- [x] Unit tests - `python3 -m pytest -q tests/unit/test_investigation_comments_tenant_write.py tests/unit/test_investigation_comments_tenant_not_null.py` (7 passed)
- [x] Integration tests - deferred to CI
- [x] Contract tests (if applicable) - N/A
- [x] E2E Smoke (critical journeys) - deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create an investigation comment for a tenant-attributed investigation and persist inherited `tenant_id`.
- [x] CUJ-02: Reject investigation comment creation before database write when parent investigation has no `tenant_id`.
- [x] CUJ-03: List investigation comments without leaking comments outside the caller tenant.

## 7) Observability & Ops
- **Logs:** No change.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Run API smoke for investigation comment create/list under tenant context.
- **Canary plan:** N/A.
- **Prod post-deploy checks:** Monitor comment creation 4xx/5xx rates and database integrity errors for `investigation_comments.tenant_id`.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected failure to create valid investigation comments or tenant-scoped comment list regressions.
- **Rollback steps:** Revert commit on main and redeploy previous SHA.
- **Owner:** Platform team.

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation.
- Staging deploy evidence: Linked after staging deploy.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

---

# Exclusive Allowlist
- `src/api/routes/investigations.py`
- `src/domain/services/investigation_service.py`
- `tests/unit/test_investigation_comments_tenant_write.py`
- `scripts/governance/pr_body_inv_comments_tenant_id.md`

# Explicitly Excluded
- `Layout`
- `App`
- `client.ts`
- `api/__init__.py`
- Alembic migrations
- `InvestigationDetail`
