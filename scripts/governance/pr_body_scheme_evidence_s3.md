# Change Ledger (CL-SCHEME-EVIDENCE-S3)

> **Start gate:** #1765 LIVE — tip `3370fd2e0`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** Prove CE firewalls CEL cannot paint ISO 9001 7.2 (and the reverse)
- **User goal:** After S1/S2, operators can file `ce-firewalls` evidence without that token covering ISO competence, and ISO 7.2 must not cover the NCSC firewalls control.
- **In scope:** Two unit tests on `any_token_matches_cell` / `clause_match_keys`.
- **Out of scope:** EXACT share, Entra, CHAS/SSIP %, Dependabot, new matching rules.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| S3-01 | CE → ISO 7.2 | Implied by framed-token family, not named | Explicit: `ce-firewalls` does not match 9001 7.2 |
| S3-02 | ISO 7.2 → CE firewalls | Same | Explicit: `9001-7.2` does not match ce/firewalls |

## 3) Compatibility & Data Safety
- Tests only. Matching behaviour unchanged.
- **Rollback strategy:** Revert merge and redeploy `3370fd2e0`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Cross-family paint | W4 framed tokens | Named CE firewalls vs ISO 7.2 regression tests |
| Invented EXACT | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `ce-firewalls` does not match ISO 9001 7.2.
- [x] AC-02: `9001-7.2` / bare `7.2` do not match CE firewalls; `ce-firewalls` does.
- [x] AC-03: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB change.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_ce_firewalls_cel_does_not_paint_iso_9001_72`
- [x] Unit: `test_iso_9001_72_cel_does_not_paint_ce_firewalls`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: CE firewalls evidence does not cover ISO 9001 7.2 (unit).
- [x] CUJ-02: ISO 9001 7.2 evidence does not cover CE firewalls (unit).

## 7) Observability & Ops
- Test-only.

## 8) Release Plan
1. Branch from LIVE tip `3370fd2e0`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Matching tests fail on main; EXACT invented.
- **Rollback steps:** Revert merge; redeploy `3370fd2e0`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1765** @ `3370fd2e0`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1765 LIVE; L11–L16 held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
