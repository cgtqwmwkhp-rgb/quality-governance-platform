# Change Ledger (CL-WCS-RLS-WC-EXP)

## 1) Summary
- **Feature / Change name:** WCS DB-02/DB-01 — WITH CHECK on existing RLS + FORCE expand (3 tables)
- **User goal (1–2 lines):** Close the write-path RLS hole on the original 12 tenant_isolation policies and extend ENABLE+FORCE+USING/WITH CHECK to three TEN2-complete owned tables (policies, audit_findings, investigation_actions).
- **In scope:** Alembic `20260711_rls_wc_exp`; `tenant_context.RLS_TABLES` SSOT expand; unit tests
- **Out of scope:** Frontend; `client.ts`; `src/services` dual-layer; near_misses NOT NULL residual; BYPASSRLS role changes; remaining owned C3/C4 RLS roll-out
- **Feature flag / kill switch:** N/A — additive PG policy rewrite; non-PG no-op; missing tables skipped

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `RLS_TABLES` inventory in `tenant_context.py` (+3 tables)
- **APIs (endpoints changed/added):** None (DB-enforced write isolation when GUC set)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** `alembic/versions/20260711_rls_with_check_expand.py` — WITH CHECK rewrite on 12 existing policies; ENABLE+FORCE+policy on policies / audit_findings / investigation_actions
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — writers must stamp matching `tenant_id` under GUC; mismatch fails closed at DB
- **Breaking changes:** Cross-tenant INSERT/UPDATE with wrong `tenant_id` now DB-denied on covered tables; unset GUC still fails closed for SELECT
- **Migration plan:** Deploy app (GUC already live from #632) then Alembic `20260711_rls_wc_exp`; smoke tenant-scoped reads/writes for policies, findings, investigation actions
- **Rollback strategy (DB):** `alembic downgrade` restores USING-only on original 12 and removes RLS from expand set; or revert merge + redeploy

## 4) Acceptance Criteria (AC)
- [x] AC-01: Existing 12 `tenant_isolation` policies recreated with matching `WITH CHECK`
- [x] AC-02: `policies`, `audit_findings`, `investigation_actions` get ENABLE + FORCE + USING/WITH CHECK
- [x] AC-03: `RLS_TABLES` SSOT length 15 includes expand set
- [x] AC-04: Unit tests cover revision chain, WITH CHECK/FORCE SQL, middleware inventory
- [x] AC-05: No `tenant_id = 1` invention in migration

## 5) Testing Evidence (link to runs)
- [x] Lint — black on touched files
- [ ] Typecheck — deferred to CI
- [x] Build — N/A (backend interpreted)
- [x] Unit tests — `TESTING=1 python3.11 -m pytest tests/unit/test_rls_with_check_expand.py tests/unit/test_tenant_context_middleware.py -q` → 16 passed
- [ ] Integration tests — deferred to CI
- [x] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Existing RLS tables retain USING predicate and gain WITH CHECK (migration source + unit)
- [x] CUJ-02: Expand tables policies/audit_findings/investigation_actions listed in FORCE+policy migration
- [x] CUJ-03: Middleware `RLS_TABLES` SSOT matches expanded inventory (15 tables)

## 7) Observability & Ops
- **Logs:** Alembic NOTICE/logger per-table apply/skip
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A — same GUC / BYPASSRLS ops model as #632

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Health/readyz + authenticated smoke on policies list, audit findings, investigation actions after migrate
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health, readiness, version SHA; spot-check tenant-scoped write/read on expand tables

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Empty tenant-scoped results / write denials for legitimate same-tenant rows after migrate
- **Rollback steps:** (1) `alembic downgrade` of `20260711_rls_wc_exp` (2) or revert merge commit and redeploy prior SHA (3) confirm GUC still bound from #632
- **Owner:** Platform / tenancy lane

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — DB/middleware inventory only
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
