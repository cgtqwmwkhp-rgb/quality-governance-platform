# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** WCS-B03 — fail-closed SMS until provider configured
- **User goal (1–2 lines):** Stop SMS tasks from reporting fake `sent` when Twilio is not configured; skip cleanly when unconfigured, and only send via real `SMSService` when credentials are present.
- **In scope:** `sms_tasks.py` fail-closed / provider-gated send path; `notification_service.py` no longer logs `sent` on failure; unit coverage in `tests/unit/test_sms_tasks.py` (commit `ca435f47`)
- **Out of scope:** `workflow_engine` SMS stub wiring (avoid conflict with #590); Twilio package pinning
- **Feature flag / kill switch:** None — fail-closed by default when provider is unconfigured

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `src/domain/services/notification_service.py` — do not treat/log SMS as `sent` on failure
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None — no DB changes
- **Workflows/jobs/queues (if any):** `src/infrastructure/tasks/sms_tasks.py` — Celery SMS task: unconfigured → `status=skipped` (never `sent`); configured → real `SMSService`; send failures → `failed` + Celery retry. No workflow YAML changes
- **Config/env/flags:** Uses existing Twilio credential env; no new feature flag
- **Dependencies (added/removed/updated):** None (Twilio pinning explicitly out of scope)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Other — behaviour correction (fail-closed / honest status); additive observability of `skipped` vs fake `sent`
- **Tolerant reader / strict writer applied?** Yes — consumers that only care about successful sends still see real `sent` only when the provider actually sends; unconfigured path returns `skipped` instead of a false positive
- **Breaking changes:** None for APIs/schemas. Task result status for unconfigured SMS changes from misleading `sent` to `skipped` (intentional honesty fix)
- **Migration plan:** None — no DB or workflow YAML changes
- **Rollback strategy (DB):** No DB change — revert commit / redeploy previous SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: Without Twilio credentials configured, SMS Celery task completes with `status=skipped` and never reports `sent`
- [x] AC-02: With Twilio credentials configured, SMS task uses real `SMSService` (no fake success path)
- [x] AC-03: Provider/send failures set `status=failed` and trigger Celery retry; `notification_service` does not log SMS as `sent` on failure
- [x] AC-04: Unit tests cover unconfigured skip, configured send path, and failure/retry behaviour (`tests/unit/test_sms_tasks.py`)
- [x] AC-05: No workflow_engine SMS stub wiring and no Twilio package pinning in this PR (deferred / conflict avoidance with #590)

## 5) Testing Evidence (link to runs)
- [x] Lint — local / pending CI on PR
- [x] Typecheck — local / pending CI on PR
- [x] Build — N/A for this backend task change (covered by CI job set)
- [x] Unit tests — `tests/unit/test_sms_tasks.py` — **7 passed locally**
- [ ] Integration tests — N/A for this change (unit-focused); CI suite linked after open
- [ ] Contract tests (if applicable) — N/A (no API/schema change)
- [ ] E2E Smoke (critical journeys) — planned on staging after merge/deploy

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Unconfigured provider — enqueue/run SMS task → result `skipped`, no outbound SMS, no fake `sent`
- [x] CUJ-02: Configured provider — SMS task invokes `SMSService`; on failure → `failed` + retry; notification path does not claim `sent`

## 7) Observability & Ops
- **Logs:** SMS task / notification paths emit honest outcomes (`skipped` when unconfigured; no `sent` on failure). Watch for increased `skipped` volume in envs missing Twilio creds (expected until configured).
- **Metrics:** No new metrics in this PR; existing task/failure signals remain the primary signal for retries
- **Alerts:** No new alerts; rely on existing Celery failure / retry monitoring
- **Runbook updates:** N/A — behaviour aligns with fail-closed ops expectation; configure Twilio env to enable real sends

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Deploy → confirm unconfigured (or creds-stripped) env yields `skipped`; with staging Twilio creds, send a controlled SMS and confirm real send + failure path does not log `sent`
- **Canary plan:** Planned — standard canary traffic % / duration per release runbook; rollback if SMS task error rate or unexpected `sent`/`failed` ratios spike vs baseline
- **Prod post-deploy checks:** Spot-check SMS task results for `skipped` vs `sent`; confirm no fake `sent` when provider unset; confirm retries on provider errors

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** SMS delivery regressions, unexpected mass `skipped`/`failed` in configured envs, or notification status incorrectness blocking ops
- **Rollback steps:** Revert commit `ca435f47` (or redeploy previous known-good SHA) and re-run deploy pipeline
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Planned post-merge
- Canary evidence (if applicable): Planned per release runbook

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API/schema/DB/YAML changes; task status honesty only
- [ ] **Gate 2:** CI green (lint/type/build/tests) — local unit tests green (7); awaiting PR CI
- [ ] **Gate 3:** Staging verification complete (evidence linked) — planned
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — planned
- [x] **Gate 5:** Production verification plan + monitoring ready — post-deploy checks and rollback documented above
