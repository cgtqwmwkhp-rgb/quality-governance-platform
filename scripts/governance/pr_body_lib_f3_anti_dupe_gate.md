# Change Ledger (CL-LIB-F3-ANTI-DUPE-GATE)

## 1) Summary
- **Feature / Change name:** Library F-3 / L-49 — anti-dupe CI gate
- **User goal (1–2 lines):** Fail PRs that introduce parallel document homes, coverage/framework/scheme twins, documents-like free-text standards columns, or SPA document URLs built outside `href_registry`.
- **In scope:** Gate script under `scripts/governance/library/`, baseline allowlist, unit tests, wire into Schema Constraint Validation CI job.
- **Out of scope:** `documents.py` upload path (F-1); alembic; converging existing multi-homes (F-7); FE URL builders; enabling Doc Graph flags.
- **Feature flag / kill switch:** None — static CI gate always on.

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None (lint only)
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None (no alembic)
- **Workflows/jobs/queues:** `.github/workflows/ci.yml` — new step on `schema-constraint-lint`
- **Config/env/flags:** `docs/governance/library_anti_dupe_baseline.json`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive CI gate; grandfather existing file homes via baseline
- **Breaking changes:** None for runtime. New ORM tables matching forbidden patterns fail CI unless baseline is updated in the same PR (reviewer-visible).
- **Migration plan:** N/A
- **Rollback strategy:** Revert PR / remove CI step

## 4) Acceptance Criteria (AC)
- [x] AC-01: Non-allowlisted table with `file_path` / `storage_key` → CRITICAL
- [x] AC-02: New `*coverage*` / `*framework*` / `*scheme*` table → CRITICAL (empty twin allowlist on tip)
- [x] AC-03: Documents-like free-text standards/clause column → CRITICAL
- [x] AC-04: Python SPA `f"/documents/{…}"` outside URL allowlist → CRITICAL
- [x] AC-05: Current tip ORM passes the gate
- [x] AC-06: Unit tests cover pass path + each failure class

## 5) Testing Evidence
- [x] `python3 scripts/validate_library_anti_dupe.py` → exit 0
- [x] `pytest tests/unit/test_library_anti_dupe_gate.py` → 9 passed
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — N/A (CI-only change; still verify MAIN tip after merge per conveyor)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Existing library / controlled / evidence file homes remain allowlisted
- [x] CUJ-02: Synthetic `document_coverage_claims` / `frameworks` fail
- [x] CUJ-03: Synthetic documents `iso_clause` fails
- [x] CUJ-04: Rogue SPA document f-string fails; `href_registry` allowed

## 7) Observability & Ops
- **Logs / metrics / alerts:** CI job output only
- **Runbook:** To permit a legitimate exception, edit `docs/governance/library_anti_dupe_baseline.json` in the same PR with owner + reason

## 8) Release Plan
- Merge after CI green (no app deploy behavior change)
- Conveyor: mark F-3 PROD/DONE only after tip CI includes the gate step green on MAIN

## 9) Rollback Plan
- **Trigger:** False-positive blocking legitimate schema work
- **Steps:** Revert merge or temporarily expand baseline with documented reason; fix gate regex if over-broad
- **Owner:** Library conveyor

## 10) Evidence Pack
- CI run(s): Linked after PR creation

## Compliance Delta
- **Standards touched:** ISO 9001 7.5 (documented information control) — prevents dual SoT drift; ISO 27001 A.5.33 protection of records (single file home)
- **Control impact:** Strengthens governance; no runtime control weakening
- **Evidence:** Unit tests + schema-constraint-lint step

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** N/A API/Data/UX (CI lint only)
- [ ] **Gate 2:** CI green
- [x] **Gate 3:** Staging verification N/A for behavior; tip CI after merge
- [x] **Gate 4:** Canary N/A
