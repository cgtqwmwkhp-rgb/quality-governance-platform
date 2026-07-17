# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Bugbot Autofix #1111 — Unknown investigation sections default to high
- **User goal (1-2 lines):** Ensure template sections without known IDs or explicit `min_level` are scoped conservatively to high investigations in backend closure gating and frontend template editing.
- **In scope:** Unknown/custom investigation section fallback level in backend service and frontend template helper; focused regression tests; this Change Ledger.
- **Out of scope:** Layout/App shell, API client wiring, `client.ts`, `api/__init__.py`, Alembic migrations, unrelated investigation comment tenant changes.
- **Feature flag / kill switch:** N/A — narrow default behavior fix.
- **Exclusive file allowlist:**
  - `src/domain/services/investigation_service.py`
  - `tests/unit/test_investigation_service.py`
  - `tests/unit/test_investigation_closure_validate.py`
  - `frontend/src/pages/investigation-builder/templateHelpers.ts`
  - `frontend/src/pages/investigation-builder/__tests__/templateHelpers.test.ts`
  - `scripts/governance/pr_body_bugbot_unknown_sections_high.md`
- **Explicit overlap exclusions:** Zero overlap with Layout/App files, `client.ts`, `api/__init__.py`, or Alembic migration files.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Investigation builder template helper now maps API sections missing `min_level` to `high`.
- **Backend (handlers/services):** `section_is_in_scope` now treats unknown section IDs without explicit `min_level` as `high`.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** No schema changes.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Conservative fallback change for missing metadata; explicit `min_level` values and known section defaults remain unchanged.
- **Tolerant reader / strict writer applied?** Yes — readers tolerate absent metadata and scope unknown sections to high.
- **Breaking changes:** None expected for templates that already persist `min_level`; unknown sections become hidden below high until metadata is supplied.
- **Migration plan:** No migration required.
- **Rollback strategy (DB):** No DB change — revert commit only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Backend unknown section IDs without `min_level` default to `high` in `section_is_in_scope`.
- [x] AC-02: Frontend API template sections without `min_level` default to `high`.
- [x] AC-03: Existing named section defaults and explicit custom `min_level` behavior remain covered.
- [x] AC-04: Focused backend and frontend regression tests cover missing/unknown section-level fallback.
- [x] AC-05: Change Ledger includes exclusive file allowlist and excluded no-overlap paths.

## 5) Testing Evidence (link to runs)
- [ ] Lint — Not run locally; no lint-surface changes beyond focused helper/tests.
- [ ] Typecheck — Not run locally; focused TypeScript test compiled through Vitest transform.
- [x] Build — N/A for this narrow fallback change.
- [x] Unit tests — `python3 -m pytest tests/unit/test_investigation_service.py -q` (8 passed).
- [x] Frontend tests — `cd frontend && npx vitest run src/pages/investigation-builder/__tests__/templateHelpers.test.ts` (4 passed).
- [x] Integration tests — N/A; no endpoint or persistence contract change.
- [x] Contract tests (if applicable) — N/A.
- [x] E2E Smoke (critical journeys) — Deferred to CI/staging.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Unknown/custom backend template section without `min_level` is only in scope for high investigations.
- [x] CUJ-02: Frontend investigation builder restores API sections without `min_level` as high-level sections.
- [x] CUJ-03: Known named section gates and explicit section `min_level` values continue to behave as before.

## 7) Observability & Ops
- **Logs:** No change.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Confirm investigation templates with missing section `min_level` do not expose unknown sections below high level; health/readiness/version checks during normal deploy.
- **Canary plan:** N/A.
- **Prod post-deploy checks:** Confirm normal investigation builder/template loading and version SHA match.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unknown/custom sections unexpectedly disappear for intended lower-level investigations without persisted `min_level`.
- **Rollback steps:** Revert the Bugbot commit and redeploy previous SHA.
- **Owner:** Platform team.

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation.
- Staging deploy evidence: Linked after staging deploy.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable).
- [ ] **Gate 2:** CI green (lint/type/build/tests).
- [ ] **Gate 3:** Staging verification complete (evidence linked).
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked).
- [x] **Gate 5:** Production verification plan + monitoring ready.
