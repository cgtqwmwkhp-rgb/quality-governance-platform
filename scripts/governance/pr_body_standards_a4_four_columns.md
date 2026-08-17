# Change Ledger (CL-STANDARDS-A4-FOUR-COLUMNS)

> **Start gate:** #1784 LIVE — tip `7cd0fcd5a621`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock: **continue A4 four columns**. Reverse of AUD-W-01 keep-3.

## 1) Summary
- **Feature / Change name:** A4 four named Audits board lanes
- **User goal:** Split Do now into Planned (`scheduled`) and Fieldwork (`in_progress`) so operators see queued work separately from work in hand. Start vs Continue stay on the card.
- **In scope:** `BOARD_WORK_LANES` + Audits board grid + AUD-W-01 tests. Do now KPI remains Planned + Fieldwork (N3).
- **Out of scope:** Entra flag. Exceptions 200. Assist triad UI. Licensed marks. S4 trees. Invented CHAS/SSIP/PM/UVDB EXACT. Fourth Findings view.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| A4-01 | Board lanes | Do now / Needs review / Closed | Planned / Fieldwork / Needs review / Closed |
| A4-02 | Card CTA | Start/Continue on Do now | Start on Planned, Continue on Fieldwork |
| A4-03 | Do now KPI | scheduled + in_progress | Unchanged set (union of Planned + Fieldwork) |
| A4-04 | Program chips | Internal / UVDB / Planet Mark / Customer | Unchanged |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** FE-only grouping. Audit statuses unchanged.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy:** Revert merge and redeploy `7cd0fcd5a621`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Board honesty | One Do now lane mixed queued and in-hand | Named Planned vs Fieldwork; not raw status column ids |
| KPI vs lanes (N3) | Do now KPI = Do now lane | Do now KPI = Planned + Fieldwork (same statuses) |
| Keep-3 lock | AUD-W-01 keep 3 | Explicit reverse after product lock |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Four named lanes Planned / Fieldwork / Review / Closed.
- [x] AC-02: `scheduled` is Planned only; `in_progress` is Fieldwork only. No `audits-board-lane-scheduled` / `in_progress` test ids.
- [x] AC-03: Start on Planned, Continue on Fieldwork.
- [x] AC-04: Do now KPI still counts scheduled + in_progress and filters that set.
- [x] AC-05: Program chips unchanged. Closed window (A5) unchanged.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `auditsBoardModel.test.ts` + `Audits.test.tsx` — 53 passed
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Scheduled run is Planned with Start; in-progress run is Fieldwork with Continue.
- [x] CUJ-02: Do now KPI of 2 (1 scheduled + 1 in_progress) still lists both and hides Closed.

## 7) Observability & Ops
- Playwright hooks: `audits-board-lane-planned`, `audits-board-lane-fieldwork`, existing review/closed + `audits-kpi-do-now`.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: `/audits` Board shows four named lanes. KPI Do now still lists scheduled + in-progress.
3. Promote PROD; verify `/api/v1/health` version = main tip; Production **Build and Deploy SUCCESS (not skipped)**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Board shows raw status columns, or Do now KPI under-counts scheduled work.
- **Rollback steps:** Revert merge commit; redeploy prior tip `7cd0fcd5a621` via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/a4-four-columns`
- Ledger: `scripts/governance/pr_body_standards_a4_four_columns.md`
- Parent LIVE: #1784 @ `7cd0fcd5a621`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
