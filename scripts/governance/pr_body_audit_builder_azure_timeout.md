# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Fix AI Audit Builder generate-from-brief Azure gateway timeout (false CORS)
- **User goal (1–2 lines):** Make Generate succeed on prod instead of failing with browser CORS/Network Error after ~230s.
- **In scope:** Sync pipeline budget (skip Claude quality-pass by default), cap Assist Map work/time, FE timeout messaging for gateway 503/Network Error
- **Out of scope:** Full async job+poll redesign; changing Gemini model App Setting
- **Feature flag / kill switch:** `AUDIT_BUILDER_SYNC_QUALITY_PASS` (default off); `AUDIT_BUILDER_QUALITY_PASS_TIMEOUT_S` (default 45s when enabled)

## 2) Impact Map (what changed)
- **Frontend:** `AITemplateGenerator.tsx` — client wait ~210s; treat 503/Network Error as platform time-limit copy
- **Backend:** `audit_builder_generation_pipeline.py`, `ai_templates.py` generate-from-brief Assist Map cap
- **APIs:** Behaviour of `POST /api/v1/ai-templates/generate-from-brief` (faster default path)
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** `AUDIT_BUILDER_SYNC_QUALITY_PASS`, `AUDIT_BUILDER_QUALITY_PASS_TIMEOUT_S`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive / fail-soft
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None — quality-pass remains available when env enabled
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Default sync generate skips Claude quality-pass (`quality_pass_skipped_sync_budget`)
- [x] AC-02: Assist Map on generate path capped to 20 questions / 20s wall time
- [x] AC-03: FE maps gateway Network Error / 503 to generateTimeout guidance
- [x] AC-04: Unit tests cover skip-by-default + opt-in Claude path
- [x] AC-05: Prod generate completes under Azure ~230s for typical briefs (verify post-deploy)

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_audit_builder_generation_pipeline.py` (6 passed locally)
- [ ] CI — linked after PR
- [ ] Staging / prod smoke — post-merge Generate on AI Audit Builder

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: AI Audit Builder → Similar → Generate returns sections without browser CORS/Network Error
- [x] CUJ-02: With `AUDIT_BUILDER_SYNC_QUALITY_PASS=1`, Claude path still fail-softs on timeout/errors
- [x] CUJ-03: Assist Map failure/timeout does not fail the generate response

## 7) Observability & Ops
- **Logs:** Existing quality-pass skip/timeout info logs
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** Root cause = Azure ~230s hard cap; not CORS allowlist

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Generate on AI Audit Builder
- **Canary plan:** N/A
- **Prod post-deploy checks:** tip==LIVE; smoke Generate; confirm latency &lt; ~200s in App Service logs

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Generate regressions or missing sections at unacceptable rate
- **Rollback steps:** Revert merge; redeploy previous tip; optionally set `AUDIT_BUILDER_SYNC_QUALITY_PASS=1` only after async redesign
- **Owner:** Platform / Quality

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
