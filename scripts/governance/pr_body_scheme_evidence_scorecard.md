# Change Ledger (CL-SCHEME-EVIDENCE-CARD-STATS)

> **Start gate:** #1766 LIVE — tip `d589d9f20`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> S4 CHAS/SSIP trees stay blocked on publisher pin.

## 1) Summary
- **Feature / Change name:** Evidence score cards keep each loaded axis when a tree is selected
- **User goal:** After S1, clicking ISO 9001 must not rewrite CE/CE+/IiP Full/Partial/%. CHAS/SSIP stay dashes.
- **In scope:** Unfiltered `getCoverage()` for score cards; withhold mashed `covered_clauses` when `by_standard` omits an id; FE tests.
- **Out of scope:** CHAS/SSIP trees, EXACT, Entra, PM/UVDB twin, Dependabot.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| CARD-01 | Score cards vs selected tree | `getCoverage(selected)` omitted other `by_standard` rows; leftover cards mashed Full from `covered_clauses` | Coverage payload stays unfiltered; each card uses its own axis |
| CARD-02 | CHAS | Honest dash (untested) | Unit-proven: no invented % |

## 3) Compatibility & Data Safety
- FE-only. Clause tree / report remain filtered to the selected standard.
- **Rollback strategy:** Revert merge and redeploy `d589d9f20`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Cross-axis score lie | Possible after S1 | CE stats survive ISO selection |
| Invented CHAS % | UI dash | Test-locked dash |
| Invented EXACT | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Selecting ISO 9001 does not change the CE card Full/Partial/%.
- [x] AC-02: Score-card coverage fetch is unfiltered.
- [x] AC-03: CHAS card has no coverage %.
- [x] AC-04: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4-pin change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `keeps CE score-card Full/Partial/% when the ISO tree is selected`
- [x] Unit: `does not invent a CHAS coverage percentage`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: CE card keeps own axis when ISO tree is selected (unit).
- [x] CUJ-02: CHAS remains an honest dash (unit).

## 7) Observability & Ops
- FE-only.

## 8) Release Plan
1. Branch from LIVE tip `d589d9f20`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Score cards blank for loaded ISO; CHAS shows a %.
- **Rollback steps:** Revert merge; redeploy `d589d9f20`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1766** @ `d589d9f20`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1766 LIVE; L11–L16 held; S4 pin not invented
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
