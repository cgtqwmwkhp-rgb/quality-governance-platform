# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** #1243 Bugbot hardening after #1242 LIVE
- **User goal (1-2 lines):** Keep autosave safe during assessment-dimension reload, make the live audit score match visible questions only, and align the analytics critical-queue heading with the uncapped KPI total.
- **In scope:** AC-01..AC-03 below
- **Out of scope:** Dependabot / older conveyor PRs; reopening already-resolved #1242 Bugbot threads
- **Feature flag / kill switch:** N/A — frontend-only behaviour fix

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `AuditExecution.tsx` — hoist visibility helpers before early returns; flush dirty save before dimension reload; `calculateVisibleRunScore` for live score
  - `AuditAnalytics.tsx` — `formatCriticalQueueHeading` uses `summary.incomplete_critical_count`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Behavioural fix only; no schema/API changes
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert deploy/commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Changing assessment dimensions while autosave is scheduled never throws; responses + applicability still persist (helpers hoisted; dirty flush before reload)
- [x] AC-02: On-screen live score only includes answers for currently visible questions
- [x] AC-03: Critical queue heading matches KPI total (`showing N of M` when list is capped at 200)

## 5) Testing Evidence (link to runs)
- [x] Unit tests (frontend) — `calculateVisibleRunScore` + `formatCriticalQueueHeading` coverage (see CI)
- [ ] Lint / typecheck / full frontend suite — CI on PR
- [x] Contract / E2E — N/A for this FE-only fix

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor edits answers, changes assessment mode/asset type → save completes without TDZ; applicability persisted; live score excludes conditionally hidden questions
- [x] CUJ-02: Compliance lead opens `/audits/analytics` with >200 incomplete critical items → KPI and queue heading agree on total

## 7) Observability & Ops
- **Logs / Metrics / Alerts / Runbook:** No change

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Smoke AuditExecution dimension change + `/audits/analytics` critical queue heading
- **Canary plan:** N/A
- **Prod post-deploy checks:** tip==LIVE; spot-check analytics heading and execution autosave after dimension edit

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Execution autosave regressions or analytics page crash
- **Rollback steps:** Revert this commit/deploy on main
- **Owner:** Platform team

## 10) Evidence Pack (links)
- Closes #1243
- Parent: #1242 (`997ce8a9` tip==LIVE before start)
- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (FE-only; no contract change)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
