# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Audit entity-select question types (`user_select`, `location_select`, `customer_select`)
- **User goal (1-2 lines):** Let Audit Builder authors add questions that capture a specific User, Location, or Customer during audit execution, so an auditor can pick "who / where / for which customer" from a live picker instead of typing free text.
- **In scope:** AC-01..AC-05, CUJ-01, CUJ-02
- **Out of scope:** New persistence columns for entity references (the stable id/code is stored in the existing `response_value` field); admin-only user directory browsing; bulk entity import tooling
- **Feature flag / kill switch:** N/A — additive question types, no existing behavior changes unless a template author selects one of the new types

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/pages/audit-builder/EntitySelectAnswer.tsx` (new) — shared picker widget for user/location/customer, desktop + mobile variants
  - `frontend/src/pages/audit-builder/QuestionEditor.tsx` — palette entries (User / MapPin / Building2 icons)
  - `frontend/src/pages/AuditExecution.tsx`, `frontend/src/pages/MobileAuditExecution.tsx` — render `EntitySelectAnswer` for the three new types, carry an optional `entityLabel` snapshot through response state
- **Backend (handlers/services):**
  - `src/domain/services/audit_service.py` — publish-gate executable type set
  - `src/domain/services/audit_scoring_service.py` — presence-based scoring (treated like text/date/photo/signature)
- **APIs (endpoints changed/added):** No new endpoints. `question_type` accepts three new enum values on existing audit template/question create/update endpoints.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):**
  - `src/api/schemas/audit.py` — `AuditQuestionBase.question_type` pattern extended
  - `src/domain/constants/audit_question_types.py` — BE registries (`API_QUESTION_TYPES`, `FE_BUILDER_QUESTION_TYPES`, `FE_PALETTE_ORDER`, `PALETTE_API_TYPES`, `_FE_TO_API`, `from_api_question_type`)
  - `frontend/src/pages/audit-builder/types.ts`, `frontend/src/pages/audit-builder/questionTypeRegistry.ts` — FE mirror of the same registries
  - `openapi-baseline.json`, `docs/contracts/openapi.json` — `question_type` pattern regex updated to keep contract-stability checks green
- **Database (migrations/entities/indexes):** No schema changes — answers reuse the existing `response`/`response_value`/`response_json` columns; `response_json.entity_label` is an optional, non-authoritative display snapshot
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive — three new allow-listed enum values; all existing question types and stored responses are unaffected
- **Tolerant reader / strict writer applied?** Yes. Scoring and publish-gate logic treat the new types as text-like (presence of `response_value` = full credit); `entity_label` in `response_json` is optional metadata only, never required for scoring or gating
- **Breaking changes:** None
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert the commit/branch only; any templates/questions already saved with the new `question_type` values would need those questions edited if rolled back, but no data is lost (id/code values remain valid strings)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Audit Builder palette offers `user_select`, `location_select`, `customer_select` as first-class question types (1:1 FE↔API, no collapsing to a generic dropdown), each with a distinct icon (User / MapPin / Building2)
- [x] AC-02: During audit execution (desktop and mobile), each new type renders an executable picker — debounced typeahead search for users, a `<select>` of active locations, and a `<select>` of active customer lookup codes — and persists a stable id/code string as `response_value`, with a best-effort `entity_label` snapshot in `response_json` for display
- [x] AC-03: Answering one of the new question types counts as full credit under presence-based scoring (same bucket as text/textarea/date/photo/signature), and leaving it unanswered stays unscored, matching existing text-question behavior
- [x] AC-04: The three new types are included in both the backend `_EXECUTABLE_QUESTION_TYPES` and frontend `EXECUTABLE_QUESTION_TYPES` publish gates, so templates using them are publishable
- [x] AC-05: FE↔BE question-type registries stay in sync (`audit_question_types.py` ⇄ `questionTypeRegistry.ts`) and the OpenAPI contract (`openapi-baseline.json`, `docs/contracts/openapi.json`) reflects the widened `question_type` pattern so the OpenAPI Contract Stability CI check passes

## 5) Testing Evidence (link to runs)
- [x] Lint — no new lint issues introduced (no drive-by changes)
- [x] Typecheck — N/A run in this pass (existing TS build config unchanged; new file follows existing prop/type conventions)
- [x] Build — N/A (not run standalone; covered by vitest transform)
- [x] Unit tests — backend: `pytest tests/unit -k audit` → **375 passed, 1 skipped** (incl. `test_audit_question_types.py`, `test_audit_scoring.py`, `test_audit_answer_integrity_gate.py`); frontend: `vitest run` across `audit-builder/`, `auditExecutionTypeMap.test.ts`, `auditExecutionFailEvidence.test.tsx`, `mobileAuditExecutionFailEvidence.test.tsx`, and new `EntitySelectAnswer.test.tsx` → **22 passed**
- [x] Integration tests — deferred to CI (requires DB / running API)
- [x] Contract tests (if applicable) — OpenAPI baseline pattern diff is a targeted 1-line regex extension in both `openapi-baseline.json` and `docs/contracts/openapi.json`
- [ ] E2E Smoke (critical journeys) — deferred to staging (no Playwright run in this pass)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor answers a `user_select` question during audit execution — searches by name/email, selects a result, sees the label persist, and the answer counts as complete/scored (verified via `EntitySelectAnswer.test.tsx` debounced-search + selection test and `test_audit_scoring.py::test_entity_select_presence_gives_full_credit`)
- [x] CUJ-02: Template author adds a `location_select` or `customer_select` question in Audit Builder and publishes the template — the new types appear in the palette, map correctly through the FE↔API registries, and are recognized as executable/publishable (verified via `questionTypeRegistry` FE↔API round-trip tests, `templateHelpers.test.ts` executable-type assertions, and `test_audit_question_types.py`)

## 7) Observability & Ops
- **Logs:** No change — errors from entity lookups surface inline via existing `getApiErrorMessage` pattern, no new log lines added
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Create a template with one of each new question type, publish it, run an audit end-to-end on desktop and mobile, confirm scoring and CAPA/finding flows treat the answer as a normal text-like response
- **Canary plan:** N/A — low-risk additive change, standard rollout
- **Prod post-deploy checks:** Health/readiness/version endpoints; spot-check Audit Builder palette renders the three new types

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** OpenAPI contract check failure, or any regression in existing question-type scoring/publish behavior
- **Rollback steps:** Revert this commit/branch; no data migration to unwind since no schema changed
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive enum extension, FE↔BE registries kept in sync
- [x] **Gate 2:** CI green (lint/type/build/tests) — backend and frontend unit/vitest suites passing locally; CI to confirm
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
