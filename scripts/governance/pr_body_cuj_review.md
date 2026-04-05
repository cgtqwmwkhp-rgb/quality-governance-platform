# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CUJ evidence pack + import triage API integration tests.
- **User goal (1-2 lines):** Capture four critical journeys and four intensive review passes; close test gap on `POST /risk-register/{id}/suggestion-triage`.
- **In scope:** `docs/evidence/CUJ_REVIEW_IMPORT_CAPA_GOVERNANCE_2026-04-05.md`, `tests/integration/test_risk_register_suggestion_triage.py`.
- **Out of scope:** OpenAPI regeneration; product is English-speaking (no locale assurance gate).
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend:** None.
- **Backend:** None.
- **APIs:** None (tests exercise existing endpoints).
- **Database:** None.
- **Workflows:** None.
- **Documentation:** New evidence / UAT artifact.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (tests + docs).
- **Breaking changes:** None.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Evidence doc defines CUJ-01–CUJ-04 and four review passes with gaps table.
- [x] AC-02: Integration tests cover accept, reject+notes, idempotent reject (400), pending list filter.
- [x] AC-03: Wiring matrix references ORM, routes, and frontend files.

## 5) Testing Evidence (link to runs)
- [x] Unit / integration: `python3.11 -m pytest tests/integration/test_risk_register_suggestion_triage.py`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Accept pending import risk (documented + integration accept path).
- [x] CUJ-02: Reject with notes (documented + integration reject path).
- [x] CUJ-03: CAPA vs triage operator clarity (documented; manual UAT).
- [x] CUJ-04: Audit action traceability (documented; existing unit coverage referenced).

## 7) Observability & Ops
- N/A — documentation references existing logging and error envelope behaviour.

## 8) Release Plan (Local -> Staging -> Prod)
- Docs-only + tests; merge to main; no production deploy required for runtime behaviour.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Flaky or environment-specific test failures.
- **Rollback steps:** Revert merge commit.
- **Owner:** Platform maintainer.

## 10) Evidence Pack (links)
- This PR; evidence file path: `docs/evidence/CUJ_REVIEW_IMPORT_CAPA_GOVERNANCE_2026-04-05.md`.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + Change Ledger complete
- [x] **Gate 1:** N/A (no contract change)
- [x] **Gate 2:** CI green expected
- [x] **Gate 3:** Staging UAT script provided (manual)
- [x] **Gate 4:** Canary N/A
- [x] **Gate 5:** N/A
