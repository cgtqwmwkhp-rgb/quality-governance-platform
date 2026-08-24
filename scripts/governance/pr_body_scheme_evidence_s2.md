# Change Ledger (CL-SCHEME-EVIDENCE-S2)

> **Start gate:** #1764 LIVE — tip `47dd04cb8`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** CEL write accepts loaded scheme catalogue keys (CE / CE+ / IiP)
- **User goal:** Operators can attach evidence to `ce-firewalls` (and peers) without the API treating those keys as invalid ISO clauses, and without opening CHAS/SSIP/PM/UVDB write.
- **In scope:** `POST /compliance/evidence/link` clause-id gate; honesty empty-state copy; unit tests.
- **Out of scope:** EXACT share, Entra, CHAS/SSIP %, Dependabot, PM/UVDB twin trees, auto-tag of scheme controls.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| S2-01 | CEL link | Only `iso_compliance_service.get_clause` | Also loaded scheme keys from S1 axis |
| S2-02 | CHAS/SSIP/PM/UVDB keys | Would 400 as invalid (accidental) | Still 400 — explicit refuse |
| S2-03 | Evidence empty copy | “linked to ISO clauses” | ISO or loaded-scheme clauses |

## 3) Compatibility & Data Safety
- No schema change. Sole CEL writer unchanged. Validation only widened to S1 loaded keys.
- **Rollback strategy:** Revert merge and redeploy `47dd04cb8`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Scheme CEL write | Trees visible, write 400 | Write to ce/cep/iip keys |
| Invented EXACT | Refused | Untouched |
| Provisional CHAS axis | Not writable | Still not writable |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `POST .../evidence/link` with `ce-firewalls` upserts a CEL row.
- [x] AC-02: `chas-CHAS 1` is still Invalid clause ID.
- [x] AC-03: Existing ISO `9001-7.5` / `9001-9.2` link test still passes.
- [x] AC-04: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_link_evidence_accepts_loaded_scheme_catalogue_keys`
- [x] Unit: `test_link_evidence_refuses_provisional_scheme_keys`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Attach document evidence to CE firewalls catalogue key (unit).
- [x] CUJ-02: ISO 9001 link path unchanged (existing spine test).

## 7) Observability & Ops
- No new flags. Failed scheme keys remain BadRequestError.

## 8) Release Plan
1. Branch from LIVE tip `47dd04cb8`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** ISO CEL writes fail; CHAS keys accepted; EXACT invented.
- **Rollback steps:** Revert merge; redeploy `47dd04cb8`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1764** @ `47dd04cb8`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1764 LIVE; L11–L16 held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
