# Change Ledger (CL-AUDITS-A3-FINDINGS-SCOPE)

> **Start gate:** #1770 LIVE — tip `29d84caf0`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** for A3 after A2 LIVE. A5b server `q=` is not this slice.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt.
> S4 CHAS/SSIP trees stay blocked. A4 stays 3 columns.

## 1) Summary
- **Feature / Change name:** Programme-scoped Open Findings + honour `/audits?clause=`
- **User goal:** Internal chip must not show tenant-wide Open Findings 100. Compliance `?clause=` must filter the Findings tab.
- **In scope:** Scope findings and Open Findings KPI to the active programme chip / customer source; honour `clause` query; tests. Count loaded in-scope findings only — do not invent a tenant number.
- **Out of scope:** Server search `q=` (A5b). Four-column lanes (A4). Entra / EXACT / Dependabot / CHAS trees. CAPA ribbon rewrite.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| A3-01 | Open Findings KPI | Tenant server total (100) while Internal chip shows 6 runs | Count open findings on the visible programme runs |
| A3-02 | Findings tab | All tenant findings (customer source only scoped) | Same programme filter as the board chips |
| A3-03 | `/audits?view=findings&clause=` | Unread | Findings tab + clause match on `clause_ids` / bounded title text |

## 3) Compatibility & Data Safety
- PX-262 tenant server total still used when no programme / customer / clause subset is active and the loaded page is truncated.
- Integer catalog `clause_ids` are not treated as clause numbers. Import strings such as `"7.2"` match.
- **Rollback strategy:** Revert merge and redeploy `29d84caf0`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Open Findings KPI vs active chip | Tenant 100 vs Internal 6 | Scoped to chip runs |
| `/compliance?clause=` deep-link | Unread on Audits | Honoured |
| Invented EXACT / CHAS % | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] ac-01: Internal chip Open Findings KPI counts findings on those runs, not the tenant server total.
- [x] ac-02: Findings tab for the Internal chip hides findings from other programmes.
- [x] ac-03: `?view=findings&clause=7.2` opens Findings and keeps matching findings only.
- [x] ac-04: Truncated tenant-wide view still uses PX-262 server total when no subset is active.
- [x] ac-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4/A4/A5b change. CAPA ribbon unchanged.
- [ ] ac-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `resolveOpenFindingsKpi` subset flag; `findingMatchesClause`; `scopeFindingsToRunIds`
- [x] Unit: Internal chip KPI 2 not 100; clause filter hides unmatched finding in `Audits.test.tsx`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] cuj-01: Six Internal runs + tenant open total 100 → Internal chip Open Findings = 2 (unit).
- [x] cuj-02: Compliance link `/audits?view=findings&clause=7.2` shows only clause 7.2 findings (unit).

## 7) Observability & Ops
- `data-testid="audits-kpi-open-findings"`
- `data-testid="audits-findings-clause-filter"`
- CAPA ribbon unchanged.

## 8) Release Plan
1. Branch from LIVE tip `29d84caf0`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Internal chip still shows tenant 100; clause deep-link shows all findings; PX-262 tenant honesty regresses.
- **Rollback steps:** Revert merge; redeploy `29d84caf0`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1770** @ `29d84caf0`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1770 LIVE; A3 continue given; A5b held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
