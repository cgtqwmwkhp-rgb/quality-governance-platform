# Change Ledger (CL-SCHEME-EVIDENCE-S1)

> **Start gate:** #1763 LIVE — tip `9a9322357`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** Own-axis Evidence trees for loaded scheme catalogues (CE / CE+ / IiP)
- **User goal:** Cyber Essentials, Cyber Essentials Plus, and Investors in People cards on `/compliance` open a real requirement tree and honest Full/Partial/Gaps against **that** axis — not an ISO clone, not a dash that pretends the catalogue is missing.
- **In scope:** `GET /compliance/standards|clauses|coverage|gaps|report` for `ce`/`cep`/`iip`; Evidence card mapping; unit tests.
- **Out of scope:** CHAS/SSIP coverage % (provisional until publisher pin). Planet Mark / UVDB twin trees. EXACT share. Entra flag. Dependabot. CEL write UX (S2).
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| S1-01 | Evidence CE/CE+/IiP cards | Honest empty: “not in the clause evidence catalogue yet” | Clickable own-axis tree; % vs 5 / 5 / 9 rows |
| S1-02 | `list_standards` | `for iso_standard in ISOStandard` only | Also emits `ce`/`cep`/`iip` from requirement-axes-v1 |
| S1-03 | CHAS/SSIP/PM/UVDB cards | Empty or specialist deep-link | Unchanged |

## 3) Compatibility & Data Safety
- No migration. Int-W5 already seeded scheme `clauses` rows. This PR **reads** the in-memory loaded axes.
- Does not import `scheme_evidence_service` from TrapGuard or ingest gate.
- **Rollback strategy:** Revert merge and redeploy prior tip `9a9322357`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Scheme Evidence honesty | Loaded axes hidden behind “not in catalogue” | Loaded axes scored on their own keys (`ce-firewalls`, `iip-IIP 7`) |
| Invented EXACT | Refused | Still refused — no exact_share change |
| CHAS/SSIP publisher pin | Provisional themes, no % | Still no % |
| PM/UVDB SoR | Specialist routes | Still specialist — mapping to Evidence API removed for pm/uvdb |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `complianceStandardIdFromFrameworkId('ce'|'cep'|'iip')` is the scheme id; `chas`/`ssip`/`pm`/`uvdb` remain null.
- [x] AC-02: `list_standards` includes ce (5), cep (5), iip (9) and does not include chas/ssip/pm/uvdb.
- [x] AC-03: Scheme coverage ignores ISO CEL (`9001-7.5` does not cover CE firewalls).
- [x] AC-04: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_scheme_evidence_service.py`
- [x] Unit: `test_wave2_compliance_spine.py` list_standards includes loaded schemes only
- [x] Frontend: `standardsMatrixFilters.test.ts` bridge + honesty nulls
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [ ] CUJ-01: Prod `/compliance` CE card opens 5-control tree (after LIVE).
- [ ] CUJ-02: CHAS/SSIP still have no coverage %.
- [x] CUJ-03: ISO path unchanged (existing list_standards ISO assertions).

## 7) Observability & Ops
- No new flags. Scheme report includes `honesty_note`.

## 8) Release Plan
1. Branch from LIVE tip `9a9322357`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** ISO Evidence regresses; CHAS shows a fake %; EXACT invented; Entra flipped.
- **Rollback steps:** Revert merge; redeploy `9a9322357`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1763** @ `9a9322357`
- Plan: scheme-evidence-360 canvas PR-S1

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1763 LIVE; L11–L16 held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
