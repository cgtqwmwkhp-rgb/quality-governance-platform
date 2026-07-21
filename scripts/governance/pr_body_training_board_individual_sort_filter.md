# Change Ledger (CL-TRAINING-BOARD-VIEW-SORT-FILTER)

## 1) Summary
- **Feature / Change name:** Board list views — four metric columns + sort/filter/drill-in
- **User goal (1–2 lines):** Give By individual / By group / By course / By module the same Complete · Overdue · % · Need columns, with sort, filter, red overdue badges, and Sheet drill-in.
- **In scope:** Person table sort/filter; course/group/module metric rollups; shared sort/filter UI; entity Sheet drill-in to people; CSV/email use visible filtered lists
- **Out of scope:** Analytics chart redesign; server-side sorting
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `TrainingMatrixGapBoard` individual/group/course/module tables; entity metric helpers + person rollup sort/filter; Sheet drill-downs
- **Backend:** None
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** UI-only; By course replaces horizon bucket columns (30d/60d/180d/OK) with the same four metrics as By individual; top-course chips still use horizon counts
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None (display columns only)
- **Migration plan:** Deploy; hard-refresh Training board
- **Rollback strategy (DB):** No DB change; revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: By individual columns are sortable/filterable; Overdue uses red destructive badge
- [x] AC-02: By group / By course / By module show Complete, Overdue, %, Need to complete with the same sort/filter pattern
- [x] AC-03: Clicking a group/course/module row opens a Sheet with metrics + people needing action; person click opens person Sheet
- [x] AC-04: Export CSV and Email everyone in filter use the currently visible filtered list for these views

## 5) Testing Evidence (link to runs)
- [x] Unit FE — person + entity metric filter/sort/rollups; moduleViewForRole Complete/Overdue/Need
- [ ] CI — after push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens By course → sees four metric columns with red overdue → sorts/filters → drills into a course Sheet
- [x] CUJ-02: Manager opens By individual → sorts by % and filters Department → export matches visible rows

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Training gap board — exercise individual/group/course/module sort, filter, drill-in
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same after hard refresh

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Tables unusable or email selection wrong
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce Training

## 10) Evidence Pack (links)
- CI run(s): after push
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — UI-only
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
