# Change Ledger (CL-TRAINING-BOARD-WAVE-A)

## 1) Summary
- **Feature / Change name:** Training board metrics SSOT + By individual columns
- **User goal (1–2 lines):** Fix the hero bar stuck at 0% by using matrix module OK%, and show Complete / Overdue / % / Need on By individual.
- **In scope:** `GET /summary`; `person_id` on compliance rows; module OK + people fully OK dual metrics; GapBoard hero from summary; roleScope click filter; By individual four columns; CSV person export
- **Out of scope:** Sheet drill-down; Analytics tab charts (Wave B)
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `TrainingMatrixGapBoard` hero + individual table; `trainingMatrixBoardHelpers` rollups; `getSummary` client
- **Backend:** `training_matrix_board.py` summary helpers; `GET /training-matrix/summary`
- **APIs:** Additive summary endpoint; compliance rows gain `person_id`
- **Schemas/contracts:** `TrainingMatrixSummaryResponse`
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API fields/endpoint
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None (hero caption semantics improved)
- **Migration plan:** Deploy; hard-refresh Training board
- **Rollback strategy (DB):** No DB change; revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Hero primary % = module OK (compliant + due_soon) / required rows
- [x] AC-02: Blank frequency cells remain excluded from denominators
- [x] AC-03: By individual shows Complete, Overdue, %, Need to complete from full required set
- [x] AC-04: Hero role click filters board via roleScope
- [x] AC-05: GET /summary returns dual metrics + horizons including d90

## 5) Testing Evidence (link to runs)
- [x] Unit BE — module OK / person rollup / summary
- [x] Unit FE — module stats, person rollups, myTrainingSummary
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens gap board → hero shows module % not stuck at people-100% 0%
- [x] CUJ-02: By individual shows four stats; horizon change keeps Complete/Need from full set

## 7) Observability & Ops
- **Logs:** Standard API
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** Map Admin Training groups for Office/Management so those hero scopes populate

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Upload present; hero % > 0 when modules in-cycle; individual columns populated
- **Canary plan:** N/A
- **Prod post-deploy checks:** GET /summary 200; board hero updates

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Hero/denominator wrong at scale
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce Training

## 10) Evidence Pack (links)
- CI run(s): after open
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
