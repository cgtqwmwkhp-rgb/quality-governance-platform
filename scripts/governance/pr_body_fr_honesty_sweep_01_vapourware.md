# Change Ledger (CL-FR-HONESTY-SWEEP-01)

> Base: `origin/main` @ `b2ff4d92f` (#1706 FR-DASH-RECENT-01 dashboard case links).
> Deletion-only honesty sweep. Frontend only — no alembic, no API surface change,
> no new flag, no new feature.

## 1) Summary

- **Feature / Change name:** FR-HONESTY-SWEEP-01 — remove three vapourware
  controls that looked like working settings and were not
- **User goal (1–2 lines):** A user who flips a switch in this product should be
  able to trust that something happened. Three surfaces broke that contract:
  they rendered a control, accepted the click, and then did nothing. This PR
  deletes them rather than leaving the user to discover the lie.
- **Problem:** Each item was demonstrably inert in the code as shipped:
  1. `/admin/notifications` rendered four channel cards (Email, Push, In-App,
     Webhook) whose toggle wrote to local `useState` and nothing else. The file
     admitted it in its own comment (`// Cosmetic channel cards below are not
     persisted`) and in on-screen copy ("illustrative only and do not persist").
     A disclaimer under a working-looking switch is not honesty — it is a
     working-looking switch.
  2. The Notification Preferences matrix offered **Weekly Summaries** —
     "Weekly digest of governance activities" — with email / push / in-app
     switches. No weekly digest job exists anywhere in the codebase. The only
     digest beat in Celery is the unrelated monthly safety-insights digest
     (`safety_insights_tasks.run_monthly_safety_insights_digest`). The toggle
     persisted into `category_preferences` and was then read by nobody.
  3. `/workflows` (Workflow Center) sat ungated in the **My Work** hub, but the
     engine behind it holds no state. `WorkflowEngine.get_pending_approvals`
     returns `[]` unconditionally, `GET /api/v1/workflows/instances` returns
     `{"instances": [], "total": 0}`, and `get_workflow_stats` reports every
     figure except pending as `None`. Worse, the Delegation tab rendered a
     **hardcoded fictional record** — `get_active_delegations` returns a literal
     "Jane Smith / Annual leave / DEL-20260115001" for every user, and the
     delegation form's "save" returned an unsaved dict. A user could read a
     colleague's name off that screen and believe cover was arranged.
- **In scope:**
  - Delete the four non-persisting channel cards from `NotificationSettings`,
    keeping the real Compliance Schedule feature-flag toggles and the real
    VAPID push-readiness panel
  - Remove the `weekly_summaries` preference row and its locale strings; drop
    the unmodelled `email_digest_*` fields from the frontend preferences type
  - Remove the `/workflows` nav entry; retire the route to a redirect and delete
    the page that could only render an empty queue and one invented delegation
  - Regression tests that fail if any of the three comes back
- **Out of scope / deliberately not done:**
  - **ADMIN-03 preference enforcement.** `category_preferences` is still stored
    and still not consulted by the dispatcher. This PR does not change that; it
    only removes the one row whose underlying feature does not exist at all.
  - **No digest job was added.** Item 2 is a removal, not an implementation.
  - **FR-APPROVALS-01 is not started.** No generic workflow engine is built,
    and no backend workflow route, service or model is touched.
  - Audit Builder, `RecentCasesPanel`, and the notification dispatcher
    (`notification_service`) — all already shipped, all untouched.
  - No alembic revision. The `email_digest_enabled` / `email_digest_frequency`
    columns and the API fields that expose them are left exactly as they are.
  - `workflowsApi` (`frontend/src/api/workflowsClient.ts`) and the `workflows.*`
    locale strings are **retained** on purpose: the backend endpoints still
    exist and FR-APPROVALS-01 will decide their contract. Only the nav entry,
    the page, and the label that named the nav entry are gone.
  - No other nav work: Assets, calendar and CG nav items are untouched, and the
    W0 nav budget is not otherwise reopened.
- **Feature flag / kill switch:** None. This is a deletion; rollback is revert.

## 2) Impact Map (what changed)

- **Frontend — item 1, `frontend/src/pages/admin/NotificationSettings.tsx`:**
  - Removed the `NotificationChannel` interface, the `channels` state, the
    `toggleChannel` handler, and the card grid that rendered them, along with
    the disclaimer paragraph that existed only to excuse them.
  - Removed the now-unused `Bell`, `Smartphone` and `Globe` icon imports.
  - Kept: the Compliance Schedule flag card (three real `PATCH
    /api/v1/feature-flags/{key}` toggles) and the `push-vapid-readiness` panel,
    which reports server state and offers no control at all.
- **Frontend — item 2:**
  - `frontend/src/pages/Notifications.tsx`: `weekly_summaries` removed from
    `CATEGORY_IDS` and `DEFAULT_CATEGORY_CHANNELS`, with a comment recording
    why it must not be re-added without a job behind it. `CategoryId` is derived
    from `CATEGORY_IDS`, so the type narrows with it.
  - `frontend/src/api/notificationsClient.ts`: `email_digest_enabled` and
    `email_digest_frequency` dropped from `NotificationPreferences` (both
    optional, both unread by any component), replaced by a comment stating that
    the API returns them but nothing enforces them.
  - `frontend/src/i18n/locales/en.json` / `cy.json`: removed
    `notifications.pref.weekly_summaries` and `..._desc` from both locales
    (parity preserved).
- **Frontend — item 3:**
  - `frontend/src/components/Layout.tsx`: **one line deleted** — the
    `/workflows` item in the My Work hub. No other nav edit.
  - `frontend/src/App.tsx`: `workflows` route now
    `<Navigate to="/actions?view=mine" replace />`, matching the existing
    retirement idiom in the same file (`my-work`, `capa`, `users`, `/risks`).
    The `WorkflowCenter` lazy import is gone.
  - `frontend/src/pages/WorkflowCenter.tsx` **deleted** (863 lines) — no longer
    reachable, and the only source of the invented delegation row.
  - `frontend/src/i18n/locales/en.json` / `cy.json`: `nav.workflow_center`
    removed from both (the nav item it labelled no longer exists).
- **Backend:** None. No route, service, model, schema or task file changed.
- **APIs:** None. `/api/v1/workflows/*` and
  `/api/v1/notifications/preferences` are byte-identical, so `openapi.json` and
  `openapi-baseline.json` are untouched.
- **Database:** None. No alembic revision; no column added, dropped or renamed.
- **Tests:**
  - NEW `frontend/src/pages/admin/__tests__/NotificationSettings.test.tsx`
    (3 tests) — first test coverage this page has ever had.
  - `frontend/src/pages/__tests__/Notifications.test.tsx` — new test proving the
    weekly-digest row does not return even when the API hands back a stored
    `weekly_summaries` value.
  - `frontend/src/components/__tests__/Layout.test.tsx` — new freeze test; My
    Work hub expectation updated; the "auto-expands the active hub" case now
    drives off `/my-reading/42` instead of the retired `/workflows/active`.
  - `frontend/src/__tests__/App.test.tsx` — new test that a bookmarked
    `/workflows` lands on `/actions?view=mine`; stale `WorkflowCenter` mock
    removed.
  - `frontend/src/pages/__tests__/WorkflowCenter.test.tsx` **deleted** (267
    lines) — it tested the KPI honesty of a page that no longer exists.
  - `tests/smoke/test_phase3_phase4_smoke.py` — renamed
    `test_workflow_center_page_loads` to
    `test_frozen_workflows_route_still_served`; the assertion is unchanged
    because the SPA still serves the path (the redirect is client-side). No
    assertion was weakened.
- **Docs:** This Change Ledger.
- **Dependencies:** None added, removed or updated.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Removal of inert UI only. Every deletion is
  backed by evidence in this repo that the control had no effect:
  - channel cards → `setChannels` was the entire handler, no `fetch`;
  - weekly digest → no scheduler entry, no task, no consumer;
  - Workflow Center → engine methods return literals; see §1.
- **No data is destroyed by deploying this.** No migration, no backfill, no
  delete statement. The `email_digest_*` columns keep their values.
- **One data-shape consequence, stated plainly:** the preferences PUT replaces
  `category_preferences` wholesale, so the first time a user toggles any row
  after this ships, a previously stored `weekly_summaries` key is dropped from
  their JSON. That key was never read by anything, so nothing observable
  changes. It is recorded here rather than left for someone to find.
- **Stored values do not resurrect the row.** `mergeCategoryPreferences`
  iterates `CATEGORY_IDS`, so a tenant whose JSON still contains
  `weekly_summaries` gets it ignored, not rendered. Covered by test.
- **Bookmarks and deep links do not 404.** `/workflows` still resolves; it
  redirects (`replace`, so Back does not bounce). A redirect was chosen over an
  "honest empty" page because an empty page would be a new component in a
  deletion-only PR, and the file already retires four other routes this way.
- **Adjacent pre-existing defect, not fixed here (out of scope):**
  `PUT /api/v1/notifications/preferences` (`notifications.py`) overwrites the
  whole `category_preferences` JSON, while `push_notifications.py` merges
  event-type flags into the same column. A save from the Notifications page can
  therefore clobber flags written through the push route. This predates this PR
  and is untouched by it; it belongs with ADMIN-03 enforcement.
- **Breaking changes:** None for any API consumer. For users: three controls
  disappear. All three did nothing, and the page-level copy that admitted as
  much disappears with them.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** No DB change. Revert the merge commit.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Admin notification channels | 4 switches that wrote to `useState` and nothing else, under a note saying so | Removed; only the 3 persisted Compliance Schedule flag toggles remain |
| Admin page test coverage | None | 3 tests, incl. one asserting every button on the page has a PATCH behind it |
| Push readiness | Real server-reported panel, plus a fake "Push Notifications" toggle beside it | Real panel only — no control, no implied switch |
| Weekly digest preference | "Weekly digest of governance activities" with 3 switches; no digest job exists | Row removed; comment records that it may not return without a job |
| Retired pref in stored JSON | Would have rendered from `category_preferences` | Ignored by `CATEGORY_IDS`; proven by test |
| `email_digest_*` in FE types | Modelled as settable preferences | Unmodelled; comment states the API returns them but nothing enforces them |
| Workflow Center nav | Ungated My Work entry to a permanently empty queue | Nav entry removed; freeze locked by test |
| Invented delegation record | Every user saw a hardcoded "Jane Smith / Annual leave" delegation | Page deleted; no fabricated record is rendered anywhere |
| `/workflows` deep link | Loaded the empty stub page | Redirects to `/actions?view=mine` |
| Workflow backend | Stub engine, empty endpoints | Unchanged and untouched — FR-APPROVALS-01 owns it |
| Nav budget | `/workflows` occupied a My Work slot | One slot returned; no other nav item added, moved or removed |

## 4) Acceptance Criteria (AC)

- [x] AC-01: `/admin/notifications` renders no Email / Push / In-App / Webhook
  channel card, and every button remaining on the page belongs to a Compliance
  Schedule flag row that issues a `PATCH`.
- [x] AC-02: The Compliance Schedule flag toggles and the VAPID readiness panel
  still render and still report server state.
- [x] AC-03: The Notification Preferences matrix offers no weekly-summary /
  digest row, even when the preferences API returns a stored `weekly_summaries`
  value.
- [x] AC-04: No digest job, scheduler entry or enforcement path was added — item
  2 is a deletion only.
- [x] AC-05: The My Work hub contains no `/workflows` link when fully expanded.
- [x] AC-06: A bookmarked `/workflows` resolves to `/actions?view=mine` rather
  than 404-ing or rendering an empty queue.
- [x] AC-07: No fabricated delegation record ships anywhere in the frontend.
- [x] AC-08: No backend source, API contract, OpenAPI baseline or alembic
  revision is modified.
- [x] AC-09: No test was skipped, loosened or deleted to go green — the one
  deleted test file tested a deleted page, and the one renamed smoke test keeps
  its original assertion.
- [x] AC-10: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

Run locally in the worktree `.worktrees/honesty-sweep-vapourware`:

- [x] **Full frontend suite** `npx vitest run` → **408 files, 2839 tests
  passed**, 0 failed, 0 skipped.
- [x] `npx tsc --noEmit` → clean.
- [x] `npm run lint` (`eslint src/ --max-warnings 0`) → clean.
- [x] `npm run i18n:check` → "All i18n keys validated (4228 keys, 601 files
  scanned)"; cy parity unchanged at 92.1%.
- [x] Backend `pytest tests/unit/test_notifications_routes.py
  tests/unit/test_workflow_engine.py` → **44 passed**, 0 skipped (proving the
  untouched backend still behaves as before).
- [x] `tests/smoke/test_phase3_phase4_smoke.py` collects 22 tests; `ruff check`
  on the file passes.
- [x] **Every new test proven to bite (negative controls, each reverted
  afterwards):**
  - Re-adding the `/workflows` nav line to `Layout.tsx` → exactly the new freeze
    test fails (1 failed / 18 passed).
  - Pointing the `workflows` route back at a page component → exactly the new
    redirect test fails (1 failed / 10 passed).
  - Restoring `NotificationSettings.tsx` from `origin/main` → exactly the new
    "no toggle that fails to persist" test fails (1 failed / 2 passed); the
    CS-flag and readiness tests still pass, confirming they assert real UI and
    not the absence of the deleted cards.
  - Re-adding `weekly_summaries` to `CATEGORY_IDS` → exactly the new digest test
    fails (1 failed / 4 passed).
- [ ] Full CI — on PR.
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge).

Not verified: no real browser was driven. The evidence for the redirect is
`window.location` after render in jsdom, not a browser navigation, and no
Playwright spec references `/workflows` or either notifications surface, so none
was updated. The smoke test that requests `/workflows` over HTTP was not run
against a live frontend; it asserts that the SPA serves the path (200/302),
which a client-side redirect does not change.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Admin opens `/admin/notifications`, sees only controls that
  persist, and toggles a Compliance Schedule flag — the `PATCH` fires and the
  new state is read back from the response.
- [x] CUJ-02: User opens Notifications → Preferences, sees the five real
  categories and no weekly-digest promise, and toggling a row still persists via
  `updatePreferences`.
- [x] CUJ-03: User expands My Work in the sidebar — Actions, My Reading and
  Compliance Passport are there; there is no Workflow Center to walk into.
- [x] CUJ-04: User follows an old `/workflows` bookmark and lands on their own
  action queue instead of an empty stub with a fictional delegation.
- [ ] CUJ-05: The same four journeys against real tenant data on staging — to
  verify on tip after deploy.

## 7) Observability & Ops

- **Test hooks:** `cs-notify-flag-*` and `push-vapid-readiness` are now asserted
  by tests as well as used by Playwright. `recent-cases-*` and other hooks are
  untouched.
- **Removed hooks:** the `workflow-stat-*` and `workflow-stats-unmeasured`
  testids disappear with the page. No spec outside the deleted test file
  referenced them (checked repo-wide).
- **Logs / Metrics / Alerts:** none new, none removed. No backend telemetry is
  affected.
- **Ops note:** `/api/v1/workflows/*` stays mounted and still answers, so any
  external caller or monitor pointed at those endpoints is unaffected. Only the
  human-facing surface is frozen.
- **Runbook updates:** none required — no operational procedure referenced the
  Workflow Center page or the cosmetic channel cards.

## 8) Release Plan

1. Open PR on tip `b2ff4d92f` (#1706 merged). **Do not merge** — this PR is
   raised for review only, per the request.
2. Merge only after the ledger / compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark FR-HONESTY-SWEEP-01 conveyor **PROD → DONE**. Merge alone is
   not done.

## 9) Rollback Plan

- **Trigger:** a user needs a control this PR removed (which would mean the
  control was doing something after all), or the `/workflows` redirect
  interferes with a journey.
- **Rollback steps:** revert the merge commit on `main` and let the pipeline
  deploy the reverted tip. Frontend-only, no schema, no flag and no data
  migration, so the revert is complete on its own — no data repair and no
  `Emergency Rollback - Production` image restore needed.
- **Owner:** Platform Engineering (Governance UX lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/honesty-sweep-vapourware`
- Base: `b2ff4d92f` (#1706)
- Files: 15 changed — 5 source, 2 locale, 5 frontend test files (1 new,
  2 deleted), 1 backend smoke test rename, 1 page deleted, this ledger
- Net excluding the ledger: **173 insertions, 1,229 deletions** across 14 files
  (the insertions are almost entirely the new test file)
- Local evidence: 2839 frontend tests green, 44 backend tests green, all four
  new tests proven to fail without their change, `tsc` / eslint / i18n clean
  (see §5)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — frontend only; no API, schema, OpenAPI baseline or
  alembic change; no exported backend surface touched; `NotificationPreferences`
  only loses two optional fields no component read
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A (no flag; deletion of inert UI)
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] `Layout.tsx` edit is a **single deleted line** (the `/workflows` nav item),
  authorised for this item only. No Assets, calendar or CG nav work; no hub
  added, reordered or renamed.
- [x] No Audit Builder / `AuditTemplateBuilder` / `audit-builder` edits
- [x] No `RecentCasesPanel.tsx` or dashboard edits (no overlap with #1706)
- [x] No `notification_service` / dispatcher edits (no overlap with #1704)
- [x] No alembic revision, no backend source, no API contract, no OpenAPI change
- [x] No ADMIN-03 preference enforcement, and no digest job — both explicitly
  deferred
- [x] No generic workflow engine work; `workflowsApi` and `workflows.*` strings
  left in place for FR-APPROVALS-01
- [x] Deletion-only discipline: the sole non-test addition is a `<Navigate>`
  element reusing the retirement idiom already present in `App.tsx`
