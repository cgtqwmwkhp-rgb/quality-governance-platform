# Change Ledger (CL-AUDITS-NNAV-SCHEMES)

> **Start gate:** #1772 LIVE — tip `7c1f87c7c`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue**. L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> S4 CHAS/SSIP trees stay blocked. Builder Wave 1 and N1 locate are not this slice. A4 stays 3 columns.

## 1) Summary
- **Feature / Change name:** Nav v2 — Audits hub, Customer & external is work, UVDB/PM enter from Standards
- **User goal:** Stop treating UVDB and Planet Mark as peer Compliance tabs. Customer audits sit with the engagement queue. Hub label is Audits.
- **In scope:** Sidebar membership and labels in `Layout.tsx`. `navItemIsActive` marks Standards current on `/uvdb` and `/planet-mark`. i18n. Layout tests.
- **Out of scope:** Deleting `/uvdb` or `/planet-mark`. Fake ISO trees / EXACT. Builder Wave 1. N1 locate. Four-column lanes. Entra / Dependabot / CHAS trees.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| NNAV-01 | Hub title | Assurance | Audits (`nav.audits_hub`). Hub id stays `assurance` |
| NNAV-02 | Audits children | Audits + Builder | Audits + Builder + Customer & external (`/customer-audits`) |
| NNAV-03 | Compliance children | Standards + UVDB + Planet Mark + Customer programme + … | UVDB / Planet Mark / Customer removed from sidebar. Routes unchanged |
| NNAV-04 | `/uvdb` / `/planet-mark` | Own sidebar tabs; Compliance expands | No tabs. Compliance expands; Standards highlighted |

## 3) Compatibility & Data Safety
- FE-only. No schema change. No new pages.
- Specialist SoR stays `/uvdb` and `/planet-mark`. Board chips still filter the one Audits engine.
- **Rollback strategy:** Revert merge and redeploy `7c1f87c7c`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Criteria vs engagement | UVDB/PM/Customer as Compliance peers | Schemes enter from Standards; Customer is engagement work |
| Invented EXACT / CHAS % | Refused | Untouched |
| Second UVDB/PM board | Refused | Untouched — routes kept, sidebar peers removed |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Audits hub children are `/audits`, `/audit-templates`, `/customer-audits`. Label Customer & external.
- [x] AC-02: `/uvdb` and `/planet-mark` are not Compliance (or Audits) sidebar children. Routes still exist.
- [x] AC-03: On `/uvdb` Compliance auto-expands and Standards is highlighted; Audits hub does not expand.
- [x] AC-04: On `/customer-audits` Audits hub auto-expands; Compliance does not.
- [x] AC-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4-pin/builder-wave/N1 change.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: hub membership in `Layout.test.tsx` (39 tests with helpers)
- [x] Unit: `isStandardsSchemePath` + Standards active on scheme homes
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens Audits and sees Audits, Builder, Customer & external (unit).
- [x] CUJ-02: Evidence-card land on `/uvdb` expands Compliance with Standards highlighted (unit).

## 7) Observability & Ops
- FE-only. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `7c1f87c7c`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** `/uvdb` or `/planet-mark` 404; Customer missing from Audits hub; fake ISO tree invented.
- **Rollback steps:** Revert merge; redeploy `7c1f87c7c`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1772** @ `7c1f87c7c`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1772 LIVE; L11–L16 held; continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
