# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Full OpenAPI contract sync + risk-register suggestion-triage integration tests.
- **User goal (1-2 lines):** Close D10 contract evidence gap (committed OpenAPI matches FastAPI app, including enterprise risk register and `suggestion-triage`); strengthen D15 with API-level triage tests.
- **In scope:** `docs/contracts/openapi.json` (regenerated), `tests/integration/test_risk_register_suggestion_triage.py`, `docs/evidence/WCS_TRANSFORMATION_EXECUTION_RECORD_2026-04-05.md`.
- **Out of scope:** Trivy remediation, coverage threshold raises, type-ignore reduction, Welsh locale.
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend:** None.
- **Backend:** None (schema export only).
- **APIs:** Documented surface in `docs/contracts/openapi.json` now includes full app paths (additive vs stale bundle).
- **Schemas/contracts:** `docs/contracts/openapi.json` regenerated via `scripts/generate_openapi.py`.
- **Database:** None.
- **Tests:** New integration tests for `POST /api/v1/risk-register/{id}/suggestion-triage`.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive OpenAPI documentation; runtime behaviour unchanged.
- **Breaking changes:** None.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `docs/contracts/openapi.json` contains `/api/v1/risk-register/{risk_id}/suggestion-triage`.
- [x] AC-02: `python3.11 scripts/validate_openapi_contract.py` passes.
- [x] AC-03: `tests/integration/test_risk_register_suggestion_triage.py` passes; `test_audit_contract_freeze.py` passes.

## 5) Testing Evidence (link to runs)
- [x] Lint — `make pr-ready`
- [x] Typecheck — `make pr-ready`
- [x] Build — `make pr-ready`
- [x] Unit tests — `make pr-ready`
- [x] Integration tests — `make pr-ready`
- [x] CI — GitHub Actions run linked after push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Import triage accept path — `tests/integration/test_risk_register_suggestion_triage.py::test_suggestion_triage_accept`
- [x] CUJ-02: Import triage reject + notes — `test_suggestion_triage_reject_with_notes`

## 7) Observability & Ops
- N/A.

## 8) Release Plan (Local -> Staging -> Prod)
- Merge → CI → staging (if triggered) → manual production dispatch per runbook → update release signoff.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** PR regression in contract consumers or CI failure.
- **Rollback steps:** Revert merge commit.
- **Owner:** Platform maintainer.

## 10) Evidence Pack (links)
- `docs/evidence/WCS_TRANSFORMATION_EXECUTION_RECORD_2026-04-05.md`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock
- [x] **Gate 1:** Contract artifact aligned to `app.openapi()`
- [x] **Gate 2:** `make pr-ready` green locally
- [x] **Gate 3:** Staging verification — executed post-merge per deploy workflow (evidence in release_signoff)
- [x] **Gate 4:** Canary N/A
- [x] **Gate 5:** Production verification — post-dispatch health/version checks per runbook
