# Change Ledger (CL-TRAINING-BOARD-INDIVIDUAL-SORT-FILTER)

## 1) Summary
- **Feature / Change name:** By individual column sort + filter
- **User goal (1–2 lines):** Let managers click column headers to sort and type in column filters to narrow the By individual people list.
- **In scope:** Sortable headers (Person, Department, Complete, Overdue, %, Need); per-column filter inputs; CSV/email-everyone use the visible filtered list
- **Out of scope:** Server-side sorting; other board views (group/course/module)
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `TrainingMatrixGapBoard` individual table; `filterPersonRollups` / `sortPersonRollups` helpers + unit tests
- **Backend:** None
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** UI-only enhancement; default sort remains Overdue descending
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** Deploy; hard-refresh Training board
- **Rollback strategy (DB):** No DB change; revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Clicking a By individual column header sorts that column; second click toggles direction
- [x] AC-02: Column filter inputs narrow the visible people list (text contains for Person/Department; exact match for numeric columns)
- [x] AC-03: Export CSV and Email everyone in filter operate on the currently visible filtered list in By individual view

## 5) Testing Evidence (link to runs)
- [x] Unit FE — filterPersonRollups / sortPersonRollups
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens By individual → sorts by % or Person and sees order change
- [x] CUJ-02: Manager filters Department = Workshop → only matching people remain; export matches that list

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open Training gap board → By individual → sort headers + type filters
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same as staging after hard refresh

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Sort/filter breaks individual table or email selection
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce Training

## 10) Evidence Pack (links)
- CI run(s): after open
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
