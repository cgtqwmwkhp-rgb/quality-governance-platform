# Change Ledger (CL-STANDARDS-CHROME-HONEST-TABS)

> **Start gate:** #1779 LIVE — tip `e151966e23fe`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **keep moving forward** after agreeing the bottom row must keep the four Evidence views.

## 1) Summary
- **Feature / Change name:** Chrome programmes keep Clause View · Evidence List · Gap Analysis · Imported Audits
- **User goal:** Clicking CHAS / SSIP / Planet Mark / UVDB selects the card and still shows the same four tabs as ISO. The body tells the truth instead of hiding the shell or inventing a tree.
- **In scope:** Selectable chrome cards. Same four tabs. Honest empty copy. Exact-scheme imported rows only. Clause-coverage APIs are not called with chas/ssip/pm/uvdb.
- **Out of scope:** S4 publisher-pinned CHAS/SSIP trees. Fake Full/Partial/Gaps or EXACT. Official trademark logos. A4. Entra. Dependabot. Hiding the tabs.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| CHT-01 | CHAS/SSIP/PM/UVDB cards | Not selectable; tabs still showed the previous ISO tree | Card selects; four tabs stay; body is programme-honest |
| CHT-02 | Gap Analysis on chrome | Would say “No gaps found” if filtered empty | Names that this is not a clause score — not zero gaps |
| CHT-03 | Clause APIs | Risk of `listClauses('chas')` | Chrome ids never sent to clause-coverage APIs |

## 3) Compatibility & Data Safety
- No schema change. No alembic. Client chrome + copy only.
- **Rollback strategy:** Revert merge and redeploy `e151966e23fe`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Same shell for every card | Bottom row could not drive the four views | Same four tabs; no fake catalogue |
| S4 / EXACT / Entra | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Click CHAS → Clause View / Evidence List / Gap Analysis / Imported Audits still mounted.
- [x] AC-02: Clause View names CHAS as not in the catalogue; ISO 7.5 is not shown as a CHAS tree.
- [x] AC-03: Gap Analysis does not say “No gaps found”.
- [x] AC-04: `listClauses` / `getReport` are not called with `chas`. Coverage % on the card stays —.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `chromeCatalogueHonesty.test.ts`
- [x] Unit: `ComplianceEvidence.test.tsx` — CHAS keeps four tabs
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: CHAS select keeps tabs and honest Clause View (unit).
- [x] CUJ-02: Gap Analysis refuses zero-gaps for CHAS (unit).

## 7) Observability & Ops
- FE copy + selection only.

## 8) Release Plan
1. Branch from LIVE tip `e151966e23fe`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Tabs hidden; CHAS shows Full/Partial/Gaps; ISO tree painted as CHAS.
- **Rollback steps:** Revert merge; redeploy `e151966e23fe`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1779** @ `e151966e23fe`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1779 LIVE; S4/Entra/A4/Dependabot held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
