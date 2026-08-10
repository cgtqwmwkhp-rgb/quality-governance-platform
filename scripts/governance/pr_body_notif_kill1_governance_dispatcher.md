# Change Ledger (CL-NOTIF-KILL1)

## 1) Summary
- **Feature / Change name:** NOTIF-KILL-1 — fold the duplicate `governance_service.NotificationService` into the canonical `notification_service.NotificationService`
- **Problem:** `src/domain/services/governance_service.py` carried a second class also named `NotificationService`. It hand-built `Notification` rows and called `db.add(...)`, bypassing the canonical service entirely. Consequences: workforce assessment and induction notifications never reached WebSocket, email or push; they never carried an `action_url`, so the email renderer (`render_notification_email_html`) had no deep link to build a CTA from; and `delivered_channels` was always empty. Two classes with the same name in the same package also meant an import could silently pick the wrong one.
- **User goal:** A supervisor who is told "Assessment submitted" gets the notification through the same channels as every other notification in the platform, with a link that opens the run.
- **In scope:** move the three workforce dispatchers (`notify_assessment_complete`, `notify_induction_complete`, `notify_competency_expiry`) onto the canonical service and route them through `create_notification`; add `tenant_id` to `create_notification`; add `assessment_run_href` / `induction_run_href` to the href registry; update the two route call sites; move and strengthen the tests.
- **Out of scope:** no Alembic migration, no Layout change, no Audit Builder file (parallel lane). No change to notification preferences, channel selection, or the email renderer.
- **Feature flag / kill switch:** none. Delivery still obeys the pre-existing `NotificationPreference` rows and `_get_delivery_channels`, so a user who has email off still gets in-app only.

## 2) Impact Map (what changed)
- **Backend (services):**
  - `src/domain/services/governance_service.py` — the duplicate `NotificationService` class is deleted (133 lines). The now-unused module logger goes with it. A docstring note records that notification dispatch must not come back here.
  - `src/domain/services/notification_service.py` — new "Workforce Governance Dispatchers" section holding the three methods, now instance methods that call `self.create_notification`. `create_notification` gains an optional `tenant_id`, which the `Notification` model already has a column for and which the old governance code was setting directly.
  - `src/domain/services/href_registry.py` — `assessment_run_href` and `induction_run_href`. Run ids are opaque strings (`asm-run-5`), not ints, so they are dedicated helpers with URL quoting rather than `_ENTITY_PATHS` entries — the same shape as the existing `audit_finding_href` / `clause_evidence_href`.
- **Backend (routes):**
  - `src/api/routes/assessments.py`, `src/api/routes/inductions.py` — import the canonical service and call `NotificationService(db).notify_*`. The dispatch now happens **after** the run is committed, not before.
- **APIs:** none changed. No route signature, request or response model is touched.
- **Schemas/contracts:** none. `create_notification` gained an optional trailing keyword argument; every existing caller is unaffected.
- **Database:** no migration. `notifications.tenant_id` and `notifications.action_url` are existing columns; this PR starts populating `action_url` for workforce notifications, which was previously always NULL there.
- **Workflows/jobs/queues:** workforce notifications can now enqueue `send_email` and `send_push_notification` Celery tasks, where before they enqueued nothing. Volume is bounded by existing per-user preferences: at most two notifications per assessment or induction completion.
- **Config/env/flags:** none.
- **Dependencies:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive on the canonical service, deletion on the duplicate. The deleted class had exactly two production import sites, both updated in this PR; a repo-wide search confirms no remaining reference.
- **Ordering change, stated plainly:** the old code called `db.add(...)` inside the request transaction and let the route commit. `create_notification` commits itself. Leaving the call where it was would have made a notification commit the half-finished assessment, and a later failure in response construction could then no longer be rolled back. So the dispatch moved to after the route's own commit. This is also the correct order on its own terms: a WebSocket push or email must not describe a run that gets rolled back.
- **Failure containment:** the dispatch stays inside `try/except` and is still swallowed and logged — a broken SMTP or Celery broker must not fail a completed assessment. The handler now also calls `db.rollback()`, because `get_db` commits at request teardown; without it a half-written notification could turn a swallowed dispatch failure into a 500 on an otherwise successful request.
- **Breaking changes:** `from src.domain.services.governance_service import NotificationService` no longer resolves. Nothing outside this PR imports it.
- **Migration plan:** N/A — no schema change.
- **Rollback strategy (DB):** no DB change. Revert the PR.

## 4) Compliance Delta
- **Tenant isolation:** preserved and made explicit. The old code set `Notification.tenant_id` by constructing the model directly; the canonical service previously had no way to express tenant scope at all, so every notification it created was tenant-NULL. `create_notification` now takes `tenant_id`, and the workforce dispatchers pass the run's tenant through. Behaviour for all pre-existing callers is unchanged — they omit the argument and still write NULL, exactly as before.
- **Deep-link safety:** `action_url` values come from the href registry, not from string building at the call site, which is the standing rule for hop hrefs. Email rendering already passes every `action_url` through `absolute_href`, which rejects `javascript:` / `data:` / bare hosts, so a DB-sourced value cannot become an unsafe `<a href>`.
- **Least-privilege links, recorded:** engineer-directed notifications deliberately carry **no** `action_url`. Every `/workforce/**` SPA route is wrapped in `RequireRole allowed={['admin','supervisor']}`, which silently `Navigate`s a non-supervisor back to `/dashboard`. Shipping the engineer a link that bounces would be a worse outcome than shipping none, so the supervisor gets the run link and the engineer gets the message only. This is recorded rather than fixed: giving engineers a first-class view of their own assessment is a product decision, not a refactor.
- **Data exposure:** no new personal data in notification bodies. The messages are byte-identical to the ones the deleted class produced, except that the induction supervisor message is now built by an `if/else` rather than a conditional expression — same two strings.
- **New egress:** workforce notifications now leave the platform by email and web push where they previously stayed in the database. Recipients are the assessment's engineer and supervisor, both already parties to the record. Channel selection is the existing shared `_get_delivery_channels`, so opt-outs are honoured.

## 5) Acceptance Criteria (AC)
- [x] AC-01: `governance_service.py` contains no `NotificationService` and no `db.add(Notification(...))`; the import fails at both former call sites unless updated.
- [x] AC-02: Assessment and induction completion notifications are created through `create_notification` and are actually delivered — `delivered_channels` is populated, not empty.
- [x] AC-03: The supervisor notification carries `action_url` from the href registry: `/workforce/assessments/{run_id}/execute` and `/workforce/training/{run_id}/execute`.
- [x] AC-04: `tenant_id` still reaches the `Notification` row for both dispatchers; existing callers of `create_notification` are unchanged.
- [x] AC-05: The run is committed before any notification is dispatched.
- [x] AC-06: A dispatcher that raises does not fail the request, and leaves the session clean.
- [x] AC-07: Every behaviour the deleted class's tests asserted is still asserted somewhere — no test was deleted to make this pass, and none was loosened.

## 6) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_workforce_notifications.py` rewritten against the canonical service: 8 tests, up from 3. New assertions cover `action_url`, actual delivery (`delivered_channels`), notification type/priority/entity, outcome-specific message text including the unknown-outcome fallback, and both competency-expiry branches. **8 passed, local.**
- [x] Unit — `tests/unit/test_workforce_completion_integrity.py` gains `test_complete_assessment_commits_before_notification_dispatch`, which asserts the literal call order `["commit", "dispatch", "rollback"]` when the dispatcher raises. **7 passed, local.**
- [x] Unit — `tests/unit/test_workforce_wave4_hardening.py`: the existing route test now asserts the dispatcher was awaited once with the exact keyword arguments, instead of only stubbing it out. **2 passed, local.**
- [x] Unit — `tests/unit/test_governance_service.py`: the seven `NotificationService` cases are removed from this file because the class is gone; each one's behaviour is re-asserted, more strictly, in `test_workforce_notifications.py`. The 18 `GovernanceService` cases are untouched. **18 passed, local.**
- [x] Unit — full backend suite: **6504 passed, 11 skipped (pre-existing), 0 failed, local.**
- [x] Contract — `tests/contract`: **441 passed, 68 skipped (pre-existing), 59 xfailed, local.**
- [x] Lint/type — `black --check src tests`, `flake8 src tests`, `isort --check-only`, `mypy src/domain/services/notification_service.py src/domain/services/href_registry.py`: all clean.
- [ ] CI after open.
- **Not verified locally:** no test exercises real SMTP, a real Celery broker, or a live WebSocket connection. Delivery is asserted at the `_deliver_in_app` seam. The new email path for workforce notifications is therefore reasoned-about, not observed end to end; staging verification below is what closes that gap.

## 7) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Supervisor completes an assessment → the run commits, engineer and supervisor notifications are created with the run's tenant, and the supervisor's carries the execute deep link.
- [x] CUJ-02: Supervisor completes an induction with "Not Yet Competent" items → both recipients get the CAPA-warning wording; the supervisor's carries the training execute deep link; `not_yet_competent_count` is preserved in `extra_data`.
- [x] CUJ-03: Assessment run has no linked engineer user → only the supervisor notification is created, exactly as before.
- [x] CUJ-04: The notification dispatcher raises → the endpoint still returns the completed run and the session is rolled back rather than left dirty.

## 8) Observability & Ops
- **Logs:** the "Notifications created for assessment %s" / "Notification created for induction %s" lines move from the `governance_service` logger to the `notification_service` logger. Dispatch failures still log with `logger.exception` from the route loggers, with the run id.
- **Metrics:** none added. Per-channel delivery failures were already recorded on the notification row itself, under `extra_data["failed_channels"]` — workforce notifications now participate in that.
- **Alerts:** none added.
- **Runbook updates:** none.

## 9) Release Plan (Local → Staging → Canary → Prod)
- **Local:** suites above.
- **Staging verification:** complete one assessment and one induction. Confirm two notification rows per run with the correct `tenant_id`, a non-null `action_url` on the supervisor row, and a non-empty `delivered_channels`. Open the supervisor's email and confirm the CTA resolves against `frontend_url` to the execute page.
- **Canary plan:** not needed — no traffic-shaped behaviour, two endpoints affected.
- **Prod post-deploy checks:** watch the Celery email queue for the first few completions, and check application logs for "Failed to send assessment completion notification".

## 10) Rollback Plan (Mandatory)
- **Rollback trigger:** assessment or induction completion starts failing; notification email volume is unexpected; deep links resolve to the wrong run.
- **Rollback steps:** revert the squash-merge. There is nothing to undo in the database — no migration, and the only data difference is that some `notifications` rows have `action_url` populated where they previously did not, which is inert once the code is reverted.
- **Owner:** Workforce / Notifications track.

## 11) Evidence Pack (links)
- CI: linked after PR creation.
- Tip base: `c38f61478`.
- Deleted duplicate for review: `governance_service.NotificationService`, previously at `src/domain/services/governance_service.py:290`.
- Role gate referenced above: `frontend/src/components/RequireRole.tsx` and the `workforce/**` routes in `frontend/src/App.tsx`.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — no contract changed
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — not used
- [ ] **Gate 5:** Production verification plan + monitoring ready
