# Change Ledger (CL-WF-CLIENT)

## 1) Summary
- **Feature / Change name:** WF-CLIENT — typed workforce spine client (matrix / tickets / requirements)
- **User goal (1–2 lines):** Let page lanes consume P0 spine APIs (analytics, training tickets, competency requirements) via `createWorkforceApi(api)` without new axios instances.
- **In scope:** Typed interfaces + namespaced methods on `workforceClient.ts`; URL wiring tests; type re-exports from `client.ts`
- **Out of scope:** Layout / nav; workforce pages/UI; backend routes/schemas; Asset Management lanes; new axios clients
- **Feature flag / kill switch:** N/A — FE client wiring only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (API client only)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — client now calls existing `/api/v1/training-tickets/`, `/api/v1/competency-requirements/`, `/api/v1/wdp-analytics/*`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** FE types aligned to TrainingTicket / CompetencyRequirement / gate fields on AssessmentRun & InductionRun
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive — flat `getWdp*` methods retained; `analytics` namespace aliases them
- **Tolerant reader / strict writer applied?** Yes — optional competency gate fields on run types
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Typed `TrainingTicket`, `CompetencyRequirement`, and paginated list wrappers match backend response shapes
- [x] AC-02: Namespaced `analytics`, `trainingTickets`, `competencyRequirements` (incl. allocate) on `createWorkforceApi(api)`; back-compat `getWdp*` kept
- [x] AC-03: AssessmentRun / InductionRun optional competency gate fields + `asset_id` on AssessmentRun; URL wiring tests pass; exclusive allowlist (no Layout / pages / backend / assets)

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `src/api/workforceClient.test.ts` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke — N/A (client-only)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Analytics namespace hits same wdp-analytics URLs as flat methods
- [x] CUJ-02: Training ticket list/get/create/update/delete paths match `/api/v1/training-tickets/`
- [x] CUJ-03: Competency requirement allocate POSTs `/{id}/allocate` with allocate body

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Import `workforceApi.trainingTickets` / `.competencyRequirements` / `.analytics` from page lanes once UI lands
- **Canary plan:** N/A
- **Prod post-deploy checks:** N/A for client-only additive change

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Client type mismatch blocking FE build
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft — client-only)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE client contracts aligned to existing spine OpenAPI
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified

## Exclusive allowlist (this PR)
- `frontend/src/api/workforceClient.ts`
- `frontend/src/api/workforceClient.test.ts`
- `frontend/src/api/client.ts` (type re-exports only)
- `scripts/governance/pr_body_wf_client.md`

**Zero overlap with Asset Management lanes.** No Layout, workforce pages, backend, or asset files.
