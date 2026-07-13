# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CUJ My Work badge counts (overdue + mine)
- **User goal (1-2 lines):** Actions view toggles show All/Mine/Overdue/My overdue counts that match list filters; summary failure never silently zeros metrics.
- **In scope:** `GET /actions/view-counts`, Actions.tsx badges + summary honesty, tests
- **Out of scope:** Layout.tsx nav badges, Workforce matrix/QR
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `Actions.tsx`, `actionsClient.ts`, `client.ts` re-export, `Actions.test.tsx`
- **Backend:** `src/api/routes/actions.py` (`/view-counts`)
- **APIs:** Added `GET /api/v1/actions/view-counts`
- **Schemas:** `ActionsViewCountsResponse` / `ActionsViewCounts`
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + UI
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: View toggles show badge counts matching Mine/Overdue filters
- [x] AC-02: Summary failure shows unavailable banner (no silent zero)
- [x] AC-03: Unit tests for response shape + FE badge/summary honesty

## 5) Testing Evidence (link to runs)
- [x] Backend unit — test_actions_view_counts.py passed
- [x] Frontend — Actions.test.tsx 8 passed / 1 skipped

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Actions → see Mine/Overdue badge totals
- [x] CUJ-02: Summary API failure → metrics unavailable (not zeros)
- [x] CUJ-03: Toggle My overdue still uses server filters

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan
- **Staging verification:** /actions badges match filtered list totals
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health + Actions smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Badge counts wrong or Actions broken
- **Rollback steps:** Revert commit, redeploy
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
