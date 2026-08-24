# Change Ledger (CL-AUDITS-N3-DO-NOW-KPI)

> **Start gate:** #1778 LIVE — tip `8875060400e`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **approve all — move forward**. Entra flag stays false. A4 stays 3 columns. Dependabot is not this belt (`#1696` is react-router 6→8, not a security patch). CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** N3 — hero KPI matches the Do now lane
- **User goal:** The In Progress tile must not under-count the board. Scheduled work is Do now, not invisible to the KPI.
- **In scope:** Hero tile label + count + click-filter use the same set as the Do now lane (`scheduled` + `in_progress`).
- **Out of scope:** A4 four columns. Entra flag. Dependabot. CAPA rewrite. Fourth view. New calendar SoR. EXACT.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| N3-01 | Hero KPI | Labelled In Progress; counted `in_progress` only | Labelled Do now; counts scheduled + in_progress |
| N3-02 | Hero click-filter | List showed `in_progress` only | List shows the same Do now set as the lane |

## 3) Compatibility & Data Safety
- No schema change. No alembic. Client KPI/filter only.
- **Rollback strategy:** Revert merge and redeploy `8875060400e`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| KPI vs lane | In Progress = 1 while Do now showed scheduled + in_progress | Same set, same count |
| A4 / Entra / Dependabot | Refused | Untouched — still 3 columns |

## 4) Acceptance Criteria (AC)
- [x] AC-01: 1 scheduled + 1 in_progress + 1 completed → Do now KPI is 2, labelled Do now, not In Progress.
- [x] AC-02: Clicking the KPI lists the two Do now runs and hides the completed run.
- [x] AC-03: Board stays 3 columns. No Entra/Dependabot/A4/CAPA rewrite.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `auditsBoardModel.test.ts` — countDoNowAudits
- [x] Unit: `Audits.test.tsx` — KPI 2 + click-filter
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Scheduled + in-progress share one KPI with the Do now lane (unit).
- [x] CUJ-02: KPI click does not invent a Planned column (unit).

## 7) Observability & Ops
- FE copy + filter only. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `8875060400e`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** KPI still counts in_progress only; A4 becomes 4 columns; Entra flag flips.
- **Rollback steps:** Revert merge; redeploy `8875060400e`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1778** @ `8875060400e`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1778 LIVE; Entra/A4/Dependabot held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
