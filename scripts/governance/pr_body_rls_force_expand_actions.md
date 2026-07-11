# Change Ledger (CL-WCS-RLS-ACT-EXP)

## 1) Summary
- **Feature / Change name:** WCS DB-01 — FORCE RLS + WITH CHECK expand (action tables)
- **User goal (1–2 lines):** Extend ENABLE+FORCE+USING/WITH CHECK to three TEN2-complete owned action child tables whose parents already have RLS (`incident_actions`, `complaint_actions`, `rta_actions`).
- **In scope:** Alembic `20260711_rls_act_exp`; `tenant_context.RLS_TABLES` SSOT expand; unit tests
- **Out of scope:** Frontend; `client.ts`; `src/services` dual-layer; near_misses NOT NULL residual; BYPASSRLS role changes; remaining owned C3/C4 RLS roll-out
- **Feature flag / kill switch:** N/A — additive PG policy create; non-PG no-op; missing tables skipped

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `RLS_TABLES` inventory in `tenant_context.py` (+3 tables)
- **APIs (endpoints changed/added):** None (DB-enforced write isolation when GUC set)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** `alembic/versions/20260711_rls_force_expand_actions.py` — ENABLE+FORCE+policy on incident_actions / complaint_actions / rta_actions
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — writers must stamp matching `tenant_id` under GUC; mismatch fails closed at DB
- **Breaking changes:** Cross-tenant INSERT/UPDATE with wrong `tenant_id` now DB-denied on covered action tables; unset GUC still fails closed for SELECT
- **Migration plan:** Deploy app (GUC already live from #632 / #747) then Alembic `20260711_rls_act_exp`; smoke tenant-scoped action reads/writes for incidents, complaints, RTAs
- **Rollback strategy (DB):** `alembic downgrade` removes RLS from expand set; or revert merge + redeploy

## 4) Acceptance Criteria (AC)
- [x] AC-01: `incident_actions`, `complaint_actions`, `rta_actions` get ENABLE + FORCE + USING/WITH CHECK
- [x] AC-02: `RLS_TABLES` SSOT length 18 includes expand set
- [x] AC-03: Unit tests cover revision chain, WITH CHECK/FORCE SQL, middleware inventory
- [x] AC-04: No `tenant_id = 1` invention in migration
- [x] AC-05: Chains from `20260711_rls_wc_exp` (#747)

## 5) Testing Evidence (link to runs)
- [x] Lint — black on touched files
- [ ] Typecheck — deferred to CI
- [x] Build — N/A (backend interpreted)
- [x] Unit tests — local pytest on RLS expand + middleware inventory
- [ ] Integration tests — deferred to CI
- [x] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Expand tables listed in FORCE+policy migration
- [x] CUJ-02: Middleware `RLS_TABLES` SSOT matches expanded inventory (18 tables)
- [x] CUJ-03: Revision chains from WC-EXP head

## 7) Observability & Ops
- **Logs:** Alembic NOTICE/logger per-table apply/skip
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A — same GUC / BYPASSRLS ops model as #632 / #747

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Health/readyz + authenticated smoke on incident/complaint/RTA action list/create after migrate
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health, readiness, version SHA; spot-check tenant-scoped action write/read

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Empty tenant-scoped action results / write denials for legitimate same-tenant rows after migrate
- **Rollback steps:** (1) `alembic downgrade` of `20260711_rls_act_exp` (2) or revert merge commit and redeploy prior SHA (3) confirm GUC still bound from #632
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
