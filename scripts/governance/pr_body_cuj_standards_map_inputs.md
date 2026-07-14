# Change Ledger (CL-CUJ-STANDARDS-MAP-INPUTS)

## File allowlist (exclusive)
- `src/api/routes/governed_knowledge.py` (signal_type filter + reject rationale soft-compat)
- `frontend/src/api/knowledgeBankClient.ts`
- `frontend/src/api/knowledgeBankClient.test.ts`
- `frontend/src/pages/KnowledgeExceptions.tsx`
- `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx`
- `frontend/src/components/StandardsAssessmentPanel.tsx`
- `frontend/src/components/__tests__/StandardsAssessmentPanel.test.tsx`
- `tests/unit/test_exceptions_signal_type_filter.py`
- `scripts/governance/pr_body_cuj_standards_map_inputs.md`

**Zero overlap** with documents-search (`Documents.tsx`) and document-version-control (`DocumentDetail` / `documents.py` / DocumentControl). Soft-compat reject body so DocumentDetail legacy callers still work.

## 1) Summary
- **Feature / Change name:** CUJ — Harden map documents/cases → standards (Assessor/GKB)
- **User goal:** Clear Map CTA on cases; Exceptions inbox uses server `signal_type` filter with honest page-cap copy; rejects carry rationale when provided.
- **In scope:** `signal_type` query on `/exceptions`; FE wiring; StandardsAssessmentPanel CTA; reject rationale prompts; tests
- **Out of scope:** DocumentDetail evidence tab rewrite; Workforce competence_gap loop; WL2 watch→Actions beyond shared client

## 2) Impact Map
- **Backend:** `list_exception_inbox` `signal_type`; reject accepts optional rationale body
- **Frontend:** Exceptions + StandardsAssessmentPanel + knowledgeBankClient
- **DB/migrations:** None

## 3) Compatibility & Data Safety
- Additive query param; reject body optional (legacy clients marked honestly in notes)
- Breaking: None for existing callers omitting body

## 4) Acceptance Criteria
- [x] AC-01: GET `/exceptions?signal_type=` filters server-side
- [x] AC-02: KnowledgeExceptions passes signalType; honesty copy says server filters ≤200
- [x] AC-03: StandardsAssessmentPanel CTA = “Map to ISO / UVDB / Planet Mark”
- [x] AC-04: Reject from panel/Exceptions requires rationale (≥3 chars)
- [x] AC-05: Unit tests for client + panel + enum/request

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_exceptions_signal_type_filter.py`
- [x] Frontend unit — knowledgeBankClient + StandardsAssessmentPanel + KnowledgeExceptions
- [ ] Integration — deferred to CI

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Exceptions inbox filters by `signal_type` server-side with honest ≤200 page-cap copy
- [x] **CUJ-02:** Case Standards panel Map CTA creates proposed links that appear in Exceptions for confirm/reject

## 7) Observability & Ops
- **Logs:** Existing GKB reject/confirm audit paths unchanged
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Filter Exceptions by signal_type; run Map CTA from a case Standards tab
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Spot-check one map + one signal_type filter

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incorrect exception filtering or Map CTA regressions
- **Rollback steps:** Revert commit and redeploy
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): Linked after push
- Staging deploy evidence: pending
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
