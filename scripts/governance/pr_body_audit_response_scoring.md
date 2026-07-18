# Change Ledger (CL-AUDIT-RESPONSE-SCORING)

## 1) Summary
- **Feature / Change name:** Audit response score/max_score derivation
- **User goal (1-2 lines):** Completed audits must persist a real score and pass/fail instead of always writing 0% / passed=false when the UI shows AUDIT PASSED.
- **In scope:** Derive score/max_score from question+answer on response create/update; backfill on complete_run; expose max_score on response schemas; send score payloads from AuditExecution; unit tests; this Change Ledger
- **Out of scope:** Historical score backfill for already-completed runs; SWA/API tipspine ops; full answer-integrity normalize from stale path11 branch
- **Feature flag / kill switch:** N/A — correctness fix

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `AuditExecution.tsx` persists `score`/`max_score` and opens completed runs on the completion proof screen (not editable execute); `auditsClient.ts` update type includes `max_score`
- **Backend (handlers/services):** `audit_scoring_service.py` derive helpers; `audit_service.py` create/update/complete enrichment; `audits.py` create_response enrichment
- **APIs (endpoints changed/added):** `POST /api/v1/audits/runs/{id}/responses`, `PATCH /api/v1/audits/responses/{id}`, complete-run scoring behavior
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AuditResponse*` schemas gain optional `max_score`
- **Database (migrations/entities/indexes):** No schema changes (column already existed)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — clients may omit score/max_score; server fills
- **Breaking changes:** None
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Response create derives `max_score` from question when omitted
- [x] AC-02: yes_no/pass_fail answers derive score full/zero vs positive_answer
- [x] AC-03: complete_run backfills missing response scores before aggregating
- [x] AC-04: AuditExecution save payload includes score/max_score
- [x] AC-05: Unit tests cover derive + existing aggregate cases (`test_audit_scoring.py`)
- [x] AC-06: Opening `/audits/:id/execute` for a completed run shows Inspection completed (not editable YES/NO)

## 5) Testing Evidence (link to runs)
- [x] Lint — black on touched Python
- [x] Typecheck — deferred to CI
- [x] Build — deferred to CI
- [x] Unit tests — `python3.11 -m pytest tests/unit/test_audit_scoring.py` → 16 passed
- [x] Integration tests — deferred to CI
- [x] Contract tests (if applicable) — OpenAPI additive field
- [x] E2E Smoke (critical journeys) — Playwright Chrome audit template CUJs on prod (pre-fix showed 0%; post-deploy re-verify)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Publish/edit 10 audit template variants in Audit Builder (IDs 6–15)
- [x] CUJ-02: Conduct + complete each template (API runs AUD-2026-0059..0068; UI runs including 0069–0079)
- [x] CUJ-03: UI Submit Audit shows PASSED while API previously stored 0% — root cause fixed in this PR

## 7) Observability & Ops
- **Logs:** Existing audit endpoint events unchanged
- **Metrics:** `audits.completed` unchanged
- **Alerts:** None
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Complete a yes/no audit → GET run shows score_percentage > 0 when answers positive
- **Canary plan:** N/A
- **Prod post-deploy checks:** Repeat CUJ-AT-01 UI execute; confirm API `passed` matches UI

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Completed audits error on response submit/complete, or scores invert unexpectedly
- **Rollback steps:** Revert merge commit on main; redeploy previous SHA for API + SWA
- **Owner:** Platform / QGP maintainers

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: After merge
- Canary evidence (if applicable): N/A
- CUJ matrix canvas: `qgp-audit-template-cuj-matrix.canvas.tsx`
- Scoring fix PR: #1158

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
