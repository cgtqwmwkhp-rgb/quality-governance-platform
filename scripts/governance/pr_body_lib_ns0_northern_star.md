# Change Ledger (CL-LIB-NS0-NORTHERN-STAR-SPECS)

## 1) Summary
- **Feature / Change name:** Library Northern Star W1 / NS-0 — check in PEL-HSEQ-5014 v6.0 FINAL authority pack + ADR-0023 amendment
- **User goal (1–2 lines):** Engineers and conveyor agents have a single in-repo authority for v6 levels, 12 functions (CTR/SVC), R01–R32, and workflow — without changing runtime seed yet.
- **In scope:** `specs/governance-library/northern-star-v6.json`, `northern-star-rules-v6.json`, README update, ADR-0023 Northern Star amendment
- **Out of scope:** Alembic; `functions.json` OPS→CTR/SVC reseed (W2); cascade_level column (W3); upload index (W5); runtime rule enforcement
- **Feature flag / kill switch:** N/A — docs/specs only

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** None (docs/specs)
- **Docs:** ADR-0023 amendment; specs README
- **Contract baseline:** Unchanged

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive files only. Live `functions.json` (11 codes incl. OPS) unchanged until W2.
- **Breaking changes:** None at runtime
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Programme authority | v1 Excel / cascade canvas fragments | v6 FINAL pack in-repo + ADR amendment |
| Function vocabulary | OPS in live seed; CTR/SVC only in Downloads | Documented collision; W2 owns reseed |
| Banded PEL / R-rules | External JSON only | Checked-in `northern-star-*.json` |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `northern-star-v6.json` present under `specs/governance-library/`
- [x] AC-02: Slim `northern-star-rules-v6.json` carries levels, 12 functions, R01–R32, workflow
- [x] AC-03: ADR-0023 documents Northern Star supersession, banded PEL, CTR/SVC, W2–W9 deferrals
- [x] AC-04: No alembic, no OpenAPI, no `functions.json` mutation in this PR

## 5) Testing Evidence (link to runs)
- [x] File presence + JSON parse (local)
- [ ] Full CI — on PR
- [ ] Staging / Prod — docs-only; tip chase after merge per conveyor

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Reader of ADR-0023 finds Northern Star amendment and wave pointers
- [x] CUJ-02: `functions.json` still lists OPS (runtime unchanged)

## 7) Observability & Ops
- None

## 8) Release Plan
- Docs/specs merge; no behaviour change until later waves consume the pack

## 9) Rollback Plan (Mandatory)
- **Trigger:** Wrong payload checked in
- **Steps:** Revert merge
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack
- Source: Downloads `PEL-HSEQ-5014 … v6.0 FINAL.xlsx` + `pel_governance_library_FINAL.json`
- Master plan canvas: `library-v6-northern-star-master-plan`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Docs/specs only — enhance ADR-0023; no twin SoT tables
- [ ] **Gate 2:** CI green
- [x] **Gate 3:** N/A behaviour — verify files on tip after merge
- [x] **Gate 4:** N/A
- [x] **Gate 5:** DONE = tip LIVE after merge (docs deploy with app tip)
