# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** WF-MATRIX — CompetencyDashboard readiness heatmap + honesty KPIs
- **User goal (1–2 lines):** HSEQ / supervisors see a peer-MyPass engineer × asset-type competency matrix with honest KPI counts (never silent zeros on failed fetch) and can drill to engineer profiles.
- **In scope:** `CompetencyDashboard.tsx` readiness command centre; analytics matrix + summary wiring; status filter; empty/error/loading + Retry; unit tests; minimal `workforce.competency.*` i18n; this Change Ledger
- **Out of scope:** `workforceClient.ts`, Layout, EngineerProfile, Calendar, Assessments, CompetenceGaps, backend/API changes, due-band computation beyond keys already present on summary
- **Feature flag / kill switch:** None — uses existing `/api/v1/wdp-analytics/*` via WF-CLIENT spine

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/workforce/CompetencyDashboard.tsx` — KPI row + skills matrix heatmap from `workforceApi.analytics.getSummary` / `getEngineerMatrix`; status filter; cell → `/workforce/engineers/:id`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (consumes existing WDP analytics)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None (uses existing `WdpSummary` / `WdpEngineerMatrix`)
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **i18n:** Minimal keys under `workforce.competency.*` only
- **Tests:** `frontend/src/pages/workforce/__tests__/CompetencyDashboard.test.tsx`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE-only; tolerant of optional `due_30` / `due_60` / `due_90` competency keys when present, else single `due` KPI
- **Tolerant reader / strict writer applied?** Yes — Promise.allSettled; partial failure surfaces unavailable KPIs / matrix separately
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert FE deploy

## 4) Acceptance Criteria (AC)
- [x] AC-01: Engineer × asset-type heatmap renders from `workforceApi.analytics.getEngineerMatrix()` (or getWdpEngineerMatrix) — not a fake local grid; cell click navigates to engineer profile
- [x] AC-02: KPI row shows engineers, active, due (30/60/90 when data allows), expired, failed, not_assessed — never silent zeros on failed fetch (shows — / unavailable + Retry)
- [x] AC-03: Distinct empty vs error vs loading states; status filter; unit tests cover failure banner + matrix render

## 5) Testing Evidence (link to runs)
- [x] Unit — `frontend/src/pages/workforce/__tests__/CompetencyDashboard.test.tsx`
- [ ] Full CI — linked after PR checks
- [ ] Staging smoke — deferred to Gate 3

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Competency Dashboard → matrix cells reflect API statuses → click cell → Engineer profile route
- [x] CUJ-02: Analytics fetch fails → error/partial banner + unavailable KPIs (not faux zeros) → Retry reloads

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Login as supervisor/admin → `/workforce/competency` (or Competency Dashboard route) → confirm matrix from live analytics; force 403/5xx → confirm banner + Retry (no silent zeros)
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Dashboard loads; KPI honesty under analytics denial

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Dashboard crash; matrix shows invented data; KPIs show 0 on API failure
- **Rollback steps:** Revert FE deploy / merge revert of this PR
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main`
- Staging deploy evidence: pending
- Depends on: WF-CLIENT (#975) analytics spine

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — consumes existing WDP analytics; no contract change
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
