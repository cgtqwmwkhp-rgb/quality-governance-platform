# Change Ledger (CL-AUDITS-A2-HONEST-KPIS)

> **Start gate:** #1769 LIVE — tip `d7a8f0466`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** for A2 (then A3 / A5b after LIVE). A4 stay-3-columns is already the board contract — not a 4-col PR.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt.
> S4 CHAS/SSIP trees stay blocked. A3 findings scope and A5b server `q=` are not this slice.

## 1) Summary
- **Feature / Change name:** Honest Audits Average Score and Closed card scores
- **User goal:** Missing scores must not paint as 0%. Real 0% still shows when the run was scored.
- **In scope:** `calculate_run_score` returns null when max_score is 0; FE omits fake 0% (`max_score <= 0` or legacy `score_percentage === 0` without max); Average Score `—` + caption. Tests.
- **Out of scope:** Programme-scoped findings / `?clause=` (A3). Four-column lanes (A4). Server search `q=` (A5b). Entra / EXACT / Dependabot / CHAS trees. In Progress KPI rewrite.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| A2-01 | Average Score KPI | `(scored.length \|\| 1)` → 0% | `—` and “Not scored in this view” until a scored run exists |
| A2-02 | Closed / List score | `score_percentage != null` shows 0% | Omit unless `auditRunIsScored` (positive max_score, or non-zero without max) |
| A2-03 | Complete with no scored answers | Writes `score_percentage = 0.0` | Writes null; `passed` stays null |

## 3) Compatibility & Data Safety
- Existing completed rows that already stored 0/0 stay in the DB; FE treats them as missing via `max_score`.
- Real 0% (`max_score > 0`) unchanged.
- **Rollback strategy:** Revert merge and redeploy `d7a8f0466`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Unscored complete reported as 0% | Yes | Missing |
| Invented EXACT / CHAS % | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: No scored runs in view → Average Score is `—` with caption Not scored in this view.
- [x] AC-02: Closed cards omit 0% when max_score is 0 or missing with percentage 0.
- [x] AC-03: Closed cards show 0% when max_score is positive.
- [x] AC-04: Empty / all-NA `calculate_run_score` returns score_percentage null, not 0.0.
- [x] AC-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4/A3/A4/A5b change.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: empty / all-NA scoring → null in `test_audit_scoring.py`
- [x] Unit: `auditRunIsScored` / average em dash in `auditsBoardModel.test.ts`
- [x] Unit: Closed fake 0% omitted; real 0% kept in `Audits.test.tsx`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Five completed internals with stored 0/0 show Average Score — and no Closed 0% glyphs (unit).
- [x] CUJ-02: A completed run with max_score 10 and score 0 still shows 0% (unit).

## 7) Observability & Ops
- No new metrics. KPI uses existing list payload `max_score`.

## 8) Release Plan
1. Branch from LIVE tip `d7a8f0466`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Real 0% hidden; Average Score stuck on — when scored runs exist; complete TypeError on unscored runs.
- **Rollback steps:** Revert merge; redeploy `d7a8f0466`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1769** @ `d7a8f0466`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1769 LIVE; A2 continue given; A3/A5b held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
