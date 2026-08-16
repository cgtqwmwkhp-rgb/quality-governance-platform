# Change Ledger (CL-AUDITS-A5-CLOSED-WINDOW)

> **Start gate:** #1767 LIVE — tip `5814fec01`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> S4 CHAS/SSIP trees stay blocked on publisher pin. A1 nav and A2/A3 KPI/findings honesty are not this slice.

## 1) Summary
- **Feature / Change name:** Audits board Closed is a recent window; List locates the rest
- **User goal:** Growing closed runs must not bury Do now / Continue. Finding AUD-… still works.
- **In scope:** Closed lane last 30 days, max 8 cards; “N more closed — open List”; search switches to List; truncation banner when `total` > loaded page. FE tests.
- **Out of scope:** Server `q=` on `/audits/runs` (A5b). Four-column lanes. Nav A1. Honest 0% KPIs (A2). Findings scope (A3). Entra / EXACT / Dependabot / CHAS trees.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| A5-01 | Board Closed | Every completed run in the loaded 100 is a card | Last 30 days, max 8, newest first |
| A5-02 | Aged / capped Closed | Invisible except by scrolling the lane | Footer to List; List still has the run |
| A5-03 | Search | Filters the board in place | Non-empty search opens List |
| A5-04 | Page cap | Silent 100-row page | Banner when total > loaded |

## 3) Compatibility & Data Safety
- FE-only. `listRuns` total already returned; no schema change.
- `moreCount` is closed runs in the **loaded set** not on the board — not a tenant-wide invention.
- **Rollback strategy:** Revert merge and redeploy `5814fec01`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Closed archive on the work board | Yes | Window + List |
| Search locate beyond loaded page | Client filter of 100 | Honest truncation; server search is A5b |
| Invented EXACT / CHAS % | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Completed runs older than 30 days are not Closed cards; footer opens List where they remain.
- [x] AC-02: At most 8 Closed cards; remainder counted as more → List.
- [x] AC-03: Typing in Search switches to List and keeps the match.
- [x] AC-04: Truncation banner when total > loaded items.
- [x] AC-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4-pin/A1-nav change.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: A5 closed board window (keep recent / cap 8) in `auditsBoardModel.test.ts`
- [x] Unit: aged-out Closed footer opens List; search switches to List; truncation banner in `Audits.test.tsx`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Aged closed Wickford run is off the board and opens from List via the more control (unit).
- [x] CUJ-02: Search for AUD-2026-0057 lands on List with the row visible (unit).

## 7) Observability & Ops
- FE-only. Truncation uses existing `total`.

## 8) Release Plan
1. Branch from LIVE tip `5814fec01`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Recent Closed cards missing; List missing aged runs; search stuck on Board.
- **Rollback steps:** Revert merge; redeploy `5814fec01`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1767** @ `5814fec01`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1767 LIVE; L11–L16 held; S4 pin not invented
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
