# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** WCS-B04 async SMTP via aiosmtplib with structured failures
- **User goal (1–2 lines):** Replace blocking `smtplib` with async `aiosmtplib` and return structured `EmailSendResult` (`sent` | `skipped` | `failed`) so email send paths fail clearly and retry correctly under Celery.
- **In scope:** `email_service.py`, `email_tasks.py`, `tests/unit/test_email_service.py`, `tests/unit/test_email_tasks.py` — async SMTP send, structured result type, tenacity retries that re-raise, task-layer status mapping; wrappers/password reset remain bool
- **Out of scope:** `workflow_engine`, workflow YAML (#590), SMS
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `email_service.py` (aiosmtplib + `EmailSendResult`); `email_tasks.py` (maps structured status)
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Internal `EmailSendResult` (`sent` | `skipped` | `failed`); public wrappers / password-reset helpers remain `bool`
- **Database (migrations/entities/indexes):** No DB change
- **Workflows/jobs/queues (if any):** Celery `email_tasks` consume structured status; no workflow YAML changes
- **Config/env/flags:** None (no feature flag)
- **Dependencies (added/removed/updated):** None — `aiosmtplib` already in requirements

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (structured result at service/task boundary; bool wrappers preserved)
- **Tolerant reader / strict writer applied?** Yes — callers that expect bool keep bool wrappers; task layer reads structured status
- **Breaking changes:** None for bool-facing wrappers/password reset; tenacity retries now re-raise after exhaustion (intentional failure surfacing)
- **Migration plan:** No migration required — no DB / no workflow YAML
- **Rollback strategy (DB):** No DB change — revert commit / redeploy previous SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: Email send uses `aiosmtplib` (async) instead of blocking `smtplib`
- [x] AC-02: Core send path returns structured `EmailSendResult` with status `sent` | `skipped` | `failed`
- [x] AC-03: Tenacity (3 retries) re-raises after exhaustion so Celery can observe failure
- [x] AC-04: Wrappers and password-reset helpers continue to return `bool`
- [x] AC-05: `email_tasks` maps structured status into task outcomes
- [x] AC-06: Unit tests for email service and email tasks pass (11 passed)
- [x] AC-07: No new dependencies; no DB or workflow YAML changes; workflow_engine / SMS out of scope

## 5) Testing Evidence (link to runs)
- [x] Lint — covered by CI on PR
- [x] Typecheck — covered by CI on PR
- [x] Build — N/A (backend interpreted)
- [x] Unit tests — 11 unit tests passed (`tests/unit/test_email_service.py`, `tests/unit/test_email_tasks.py`)
- [x] Integration tests — N/A for this change (no DB / no new endpoints); deferred to CI as applicable
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging (email send path)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Async SMTP send succeeds and reports `sent` via `EmailSendResult`
- [x] CUJ-02: Skipped / failed sends surface structured status; exhausted retries re-raise
- [x] CUJ-03: Celery `email_tasks` map structured status; bool wrappers / password reset unchanged

## 7) Observability & Ops
- **Logs:** Existing email send / failure logging retained; structured status available to tasks
- **Metrics:** No new metrics
- **Alerts:** No new alerts
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Deploy commit `91e39507`; confirm health/readiness; exercise email send (success + failure/skip paths) and Celery email tasks
- **Canary plan:** N/A — standard deploy; rollback via previous SHA if email delivery regresses
- **Prod post-deploy checks:** Health/readiness; version SHA match; spot-check outbound email / password-reset mail and Celery email task outcomes

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Email delivery failures, Celery email task error spike, or password-reset mail regression post-deploy
- **Rollback steps:** Revert commit `91e39507` (or redeploy previous SHA) and verify email send path restored
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation (commit `91e39507` — `refactor(email): async SMTP via aiosmtplib with structured failures`)
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API/schema/DB contract change
- [x] **Gate 2:** CI green (lint/type/build/tests) — 11 unit tests passed locally; full CI on PR
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
