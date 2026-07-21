# Change Ledger (CL-TRAINING-BOARD-WAVE-B)

## 1) Summary
- **Feature / Change name:** Person drill-down Sheet + Analytics tab + portal label alignment
- **User goal (1–2 lines):** Click a person for full training breakdown and nudge email; see Analytics charts for group compliance and 30/90-day due — all inside the existing Gap Board.
- **In scope:** `GET /people/{id}/compliance`; Sheet drill-down; Analytics view (SVG bars/pie/due); notify gaps = Need (not due_soon); PortalWork / My training OK language
- **Out of scope:** Historical trend snapshots; executive `/analytics` page
- **Feature flag / kill switch:** N/A
- **Depends on:** #1225 (Wave A) — merge A first or stack this PR

## 2) Impact Map (what changed)
- **Frontend:** GapBoard Sheet + Analytics tab + `trainingMatrixCharts.tsx`; PortalWork gap/OK filters
- **Backend:** Person compliance endpoint; notify uses `is_gap_status`
- **APIs:** `GET /training-matrix/people/{person_id}/compliance`
- **Schemas/contracts:** `TrainingMatrixPersonComplianceResponse`
- **Database:** None
- **Dependencies:** None (uses existing Sheet)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint
- **Breaking changes:** None (notify no longer emails due_soon-only people as gaps — intentional)
- **Migration plan:** Deploy after Wave A
- **Rollback strategy (DB):** No DB change; revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Click person opens Sheet with Complete/Overdue/%/Need + module lists with Passed/QGP due
- [x] AC-02: Email to complete disabled with reason when unmapped / no email / no gaps
- [x] AC-03: Analytics tab shows compliance vs gap bars, status pie, 30/90 due
- [x] AC-04: Portal My Work “Needs attention” uses gap statuses (due_soon stays in-cycle)
- [x] AC-05: No new chart npm dependency; no Insights microsite

## 5) Testing Evidence (link to runs)
- [x] Unit BE board helpers (Wave A parity retained)
- [x] Unit FE board helpers
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens individual → clicks person → Sheet → Email (or skip reason)
- [x] CUJ-02: Manager opens Analytics → sees group bars + 30/90 due from summary

## 7) Observability & Ops
- Standard API errors; toast on Sheet load failure

## 8) Release Plan (Local → Staging → Canary → Prod)
- Merge after #1225 green; staging hard-refresh Training → gaps
- **Canary plan:** N/A
- **Prod post-deploy checks:** Sheet opens; Analytics tab renders; notify skip reasons clear

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Sheet/API errors or wrong email targeting
- **Rollback steps:** Revert this PR (Wave A can remain)
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
