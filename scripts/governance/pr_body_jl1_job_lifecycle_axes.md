# Change Ledger (CL-JL1-JOB-LIFECYCLE-AXES)

## 1) Summary
- **Feature / Change name:** JL-1 — Job Lifecycle axes pack (Job Type / Lane / Step + cell document refs)
- **User goal (1–2 lines):** Land editable JL process vocabulary and cell → library document memberships behind `job_lifecycle`, with Entity360 `origin=job` bidirectional from day one — without inventing a second org SSOT.
- **In scope:** Alembic migration + RLS; models; `/job-lifecycle` CRUD/read APIs; `job:read` / `job:author`; admin grant hand-back 82→84; Entity360 JobLifecycleProducer; unit tests
- **Out of scope:** JL-2 swimlane UX; enabling `job_lifecycle` in prod/stg; department annotation column; LookupOption axis binding; new org-unit entity; DG-3
- **Feature flag / kill switch:** `job_lifecycle` / `JOB_LIFECYCLE_ENABLED` — **default OFF** (pre-registered in X-0). Flag-off → JL routes 404.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (no JL-2 UX)
- **Backend (handlers/services):** `job_lifecycle` routes + `JobLifecycleService`; Entity360 `JobLifecycleProducer` registered
- **APIs (endpoints changed/added):** `/api/v1/job-lifecycle/job-types|lanes|steps|cells…` (flag-gated)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Job Type / Lane / Step / Cell DTOs
- **Database (migrations/entities/indexes):** `20261019_job_lifecycle_axes` — `job_types`, `job_lanes`, `job_steps`, `job_cells`, `job_cell_documents` + FORCE RLS
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Wiring only for existing `job_lifecycle` (no new flags; remains default off)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive schema + API behind default-off flag; authz tokens additive (admin grant proposal 84)
- **Tolerant reader / strict writer applied?** Yes — cell payload is `library_document_id[]` only; unknown docs rejected on write
- **Breaking changes:** None while flag off. Enabling flag requires grant of `job:read` / `job:author`
- **Migration plan:** Single revision `20261019_job_lifecycle_axes` revises `20261018_doc_one_primary` (never parallel)
- **Rollback strategy (DB):** Soft-delete axes; downgrade drops JL tables; flag-off 404s routes without data loss until downgrade

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| JL axis identity | Unlocked / ADR-only | JL `code` tables (ADR-0022) — not LookupOption / dept / org entity |
| Cell document SSOT | N/A | Junction `job_cell_documents.library_document_id` → library `documents` |
| Org SSOT risk | Belt non-goal | No department annotation column in JL-1 |
| Entity360 `origin=job` | Hop origin reserved; no producer | Bidirectional producer day one (empty lists OK) |
| JL RBAC | Comment stub used `document:read` for `job_step` hops | Enforced `job:read` / `job:author`; hop map uses `job:read` |
| Admin grant | 82-token proposal | 84-token proposal (+`job:read`,`job:author`) — still NOT APPLIED |
| Flag-off JL | Pre-registered catalogue only | Routes 404 when `job_lifecycle` off |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Job type / lane / step tables with tenant-scoped `code` identity; no LookupOption / department identity columns
- [x] AC-02: Cells hold library document memberships only (junction); no embedded document bodies
- [x] AC-03: Single Alembic revision; JL tables in `RLS_TABLES` + `HARDENING_MIGRATIONS`
- [x] AC-04: Routes gated by `job_lifecycle` (default off → 404); `job:read` / `job:author` enforced
- [x] AC-05: Catalogue + admin grant hand-back updated (82→84); grant count assertions updated
- [x] AC-06: Entity360 JobLifecycleProducer registered bidirectional day one for `document` + `job_step`
- [x] AC-07: No JL-2 swimlane UX; flag not enabled in prod/stg by this PR

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_job_lifecycle_jl1.py` + authz/admin grant/RLS registry suites
- [ ] Integration — CI
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flag enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag off → JL routes 404
- [x] CUJ-02: Axis models expose `code` identity; reject org-SSOT columns by schema
- [x] CUJ-03: Entity360 `job` producer always returns upstream + downstream lists

## 7) Observability & Ops
- **Logs:** Producer errors become Entity360 source `error` (existing composer path)
- **Metrics:** No new metrics in this PR
- **Alerts:** None new
- **Runbook updates:** Keep `JOB_LIFECYCLE_ENABLED` off until bake; apply 84-token admin grant before enabling flag in any environment (`docs/data/admin-role-permissions-grant.md`)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; `job_lifecycle` remains off unless bake; migration applied
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm `job_lifecycle` still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** JL 500s with flag on; authz lockout for admins missing `job:*` after enablement
- **Rollback steps:** Set `JOB_LIFECYCLE_ENABLED=false`; redeploy prior image if needed; DB downgrade only if tables must be removed
- **Owner:** Platform Engineering (Doc Graph × Job Lifecycle) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (ADR-0022 axes; cells = library_document_id[])
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
