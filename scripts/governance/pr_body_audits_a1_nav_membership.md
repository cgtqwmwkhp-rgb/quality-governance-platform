# Change Ledger (CL-AUDITS-A1-NAV-MEMBERSHIP)

> **Start gate:** #1768 LIVE — tip `b021d3986`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** for A1. L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> S4 CHAS/SSIP trees stay blocked on publisher pin. A2 honest KPIs, A3 findings scope, A4 four-column lanes, and A5b server `q=` are not this slice.

## 1) Summary
- **Feature / Change name:** Specialist SoR homes under Compliance; Audits work stays Assurance
- **User goal:** UVDB, Planet Mark, and Customer programme sit with Standards, not as extra audit products.
- **In scope:** Sidebar membership in `Layout.tsx`. Nav label Customer programme. Routes unchanged. Layout tests.
- **Out of scope:** New routes. Twin UVDB/PM kanbans. Moving `/audits` under Compliance. Honest 0% KPIs (A2). Findings `?clause=` (A3). Four-column lanes (A4). Server search (A5b). Entra / EXACT / Dependabot / CHAS trees.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| A1-01 | Assurance hub | Audits, Builder, UVDB, Planet Mark, Customer Audits | Audits + Builder only |
| A1-02 | Compliance hub | Standards / IMS / exceptions / schedule | Same, plus `/uvdb`, `/planet-mark`, `/customer-audits` after Standards |
| A1-03 | Customer nav label | Customer Audits | Customer programme (chip on `/audits` stays Customer) |
| A1-04 | Routes | `/uvdb` `/planet-mark` `/customer-audits` `/audits` | Unchanged |

## 3) Compatibility & Data Safety
- FE-only. No schema change. No new pages.
- Specialist pages keep their SoR. Board chips still filter the one Audits engine.
- **Rollback strategy:** Revert merge and redeploy `b021d3986`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Criteria vs engagement in the sidebar | Mixed in Assurance | Criteria homes under Compliance; engagement under Assurance |
| Invented EXACT / CHAS % | Refused | Untouched |
| Second UVDB/PM board | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Assurance children are `/audits` and `/audit-templates` only.
- [x] AC-02: `/uvdb`, `/planet-mark`, and `/customer-audits` are Compliance children; routes unchanged.
- [x] AC-03: Sidebar label is Customer programme; `/audits` chip stays Customer.
- [x] AC-04: On `/uvdb` the Compliance hub auto-expands; Assurance does not.
- [x] AC-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4-pin/A2-KPI change.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: hub membership + Customer programme label in `Layout.test.tsx`
- [x] Unit: `/uvdb` expands Compliance, not Assurance
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens Assurance and sees Audits + Builder only (unit).
- [x] CUJ-02: Evidence-card land on `/uvdb` expands Compliance with the specialist home selected (unit).

## 7) Observability & Ops
- FE-only. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `b021d3986`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Specialist homes missing from nav; Audits kanban moved; extra UVDB/PM board invented.
- **Rollback steps:** Revert merge; redeploy `b021d3986`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1768** @ `b021d3986`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1768 LIVE; L11–L16 held; A1 continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
