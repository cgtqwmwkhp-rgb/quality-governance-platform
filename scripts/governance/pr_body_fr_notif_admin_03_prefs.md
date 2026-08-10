# Change Ledger (CL-FR-NOTIF-ADMIN-03)

> Base: `origin/main` @ `5cd4a43fb` (#1707 FR-HONESTY-SWEEP-01, which itself sits on
> #1704 KILL-1 canonical dispatcher).
> Backend enforcement + a merge-semantics fix. **No alembic revision. No new
> column. No new settings table.** Two locale strings changed so the on-screen
> promise matches what is now enforced.

## 1) Summary

- **Feature / Change name:** FR-NOTIF-ADMIN-03 — notification category
  preferences and quiet hours actually gate delivery on the canonical dispatcher
- **User goal (1–2 lines):** A user who turns off "Audit Notifications → email",
  or sets quiet hours 22:00–07:00, should stop being emailed and stop being
  buzzed overnight. Until this PR both settings were stored faithfully and then
  ignored by the only code that sends anything.
- **Problem:** Three defects, all provable in the code as shipped on
  `5cd4a43fb`:
  1. **`category_preferences` was write-only.**
     `NotificationService._get_delivery_channels` read `email_enabled`,
     `sms_enabled` and `push_enabled` and nothing else. The five per-category
     channel toggles on the Notifications → Preferences tab persisted into
     `category_preferences` and were then read by no delivery code anywhere.
     #1707 §"Out of scope" recorded this explicitly and left it for this item.
  2. **Quiet hours were decorative.** `quiet_hours_enabled`,
     `quiet_hours_start` and `quiet_hours_end` exist on
     `notification_preferences` and are editable through both preference APIs.
     No line of code compared the current time to them. A user could set
     22:00–07:00 and still be pushed and SMS'd at 03:00.
  3. **The prefs clobber (found during #1707).**
     `PUT /api/v1/notifications/preferences` did
     `setattr(prefs, "category_preferences", value)` — a wholesale replace —
     while `PUT /api/v1/notifications/push/preferences` merged flat event-type
     flags into the same JSON column. The frontend always sends the full
     five-category map on save, so any save from the Notifications page silently
     deleted `incident_alerts`, `compliance_updates` and `mentions` written
     through the push route. Asymmetric data loss between two surfaces sharing
     one column.
- **In scope:**
  - New pure rules module `notification_preferences.py`: category-per-type map,
    both stored value shapes, quiet-hours window arithmetic, and one merge
    function used by both write surfaces
  - `NotificationService` consults it on every `create_notification` — including
    when the caller passed explicit `channels=`
  - Merge-not-clobber on `PUT /api/v1/notifications/preferences`; the push route
    switched onto the same shared helper so the two cannot drift apart again
  - A `suppressed_channels` audit trail on the notification row when a
    preference held a channel back
  - Tests: 63 in the two touched/added unit files, incl. negative controls
- **Out of scope / deliberately not done:**
  - **No alembic revision, and none is required.** Every field enforced here
    already exists on `notification_preferences`
    (`category_preferences`, `quiet_hours_enabled/_start/_end`). No second
    alembic head; no column added, widened or renamed.
  - **No new settings table.** The existing `NotificationPreference` model is
    the store, exactly as briefed.
  - **N1 notification inventory UI and N2 feature flags are not started here.**
  - `Layout.tsx` / nav: untouched. Audit Builder: untouched. Dashboard
    `RecentCasesPanel`: untouched. `admin/NotificationSettings` cosmetic cards:
    already deleted in #1707 and not resurrected.
  - **`WorkflowRule` is not wired in.** The brief allowed enhancing
    "WorkflowRule/prefs model"; the prefs model is the one that actually holds
    per-user consent, and `workflow_rules` has no relationship to
    `notification_preferences` and no per-user notification consent to enhance
    (`WorkflowEngine` queues Celery email directly and never touches
    `NotificationPreference`). Enhancing the prefs model was the smaller, real
    change; inventing a link to `workflow_rules` would have been scope for its
    own sake. Stated here rather than silently skipped.
  - **`document_updates` is still a no-op toggle** — see §3.
  - **Email is not deferred during quiet hours** — see §3.
  - Notification paths that bypass the canonical service (compliance-schedule
    sweep task, standards-assessment notifications, document campaigns) insert
    `Notification` rows directly and are **not** covered — see §3.
- **Feature flag / kill switch:** None, deliberately. This makes stored consent
  effective; hiding that behind a flag would leave the dishonest path as the
  default. `NOTIFICATION_QUIET_HOURS_TIMEZONE` is a config knob, not a gate:
  quiet hours only apply when a user has enabled them.

## 2) Impact Map (what changed)

- **NEW `src/domain/services/notification_preferences.py` (358 lines):** pure,
  DB-free, no ORM writes.
  - `CATEGORY_BY_TYPE` — which category owns each `NotificationType`.
    `assignment` / `reassignment` / `action_assigned` →
    `assignment_notifications`; `action_due_soon` / `action_overdue` →
    `action_reminders` (they are reminders, not assignments); the four `audit_*`
    → `audit_notifications`; the three `incident_*` plus `sos_alert` /
    `riddor_incident` → `incident_alerts`; `compliance_alert` /
    `certificate_expiring` / `certificate_expired` → `compliance_updates`;
    `mention` → `mentions`.
  - `categories_for()` — adds `high_priority_alerts` for `HIGH` priority on top
    of the type's own category, so either toggle can hold a channel back.
  - `PreferenceSnapshot.from_row()` — read-only view built with `getattr`
    defaults, so a partially-populated row degrades to "no opinion" instead of
    raising mid-dispatch.
  - `filter_channels()` — returns a `ChannelDecision(allowed, suppressed)` where
    `suppressed` maps channel → reason (`category:<id>` or `quiet_hours`).
  - `merge_category_preferences()` — the single merge rule (see §3).
  - `parse_hhmm()` / `in_quiet_window()` / `is_quiet_hours()` — bounds parsing
    and window arithmetic including the across-midnight case.
  - `_now_utc()` exists as a one-line clock seam so quiet-hours tests freeze
    time instead of racing it.
- **`src/domain/services/notification_service.py`:**
  - `_get_delivery_channels` split into `_load_preferences` (one query),
    `_channels_from_toggles` (the previous channel-toggle logic, unchanged) and
    `_resolve_delivery_channels` (toggles → category gate → quiet-hours gate).
    `_get_delivery_channels` is kept as a thin wrapper so its existing callers
    and tests are unaffected.
  - `create_notification` now resolves channels **before** inserting the row,
    because `extra_data` is a plain `JSON` column: writing
    `suppressed_channels` at construction time means SQLAlchemy actually
    persists it, rather than relying on an in-place mutation it does not track.
  - Explicit `channels=` arguments are now gated too. Callers pass channels to
    say which channels a message *suits* (`create_status` → in-app only), not to
    assert the user consented to be interrupted on them. Without this,
    `create_status`, the compliance-schedule assignment notifier
    (`[IN_APP, EMAIL]`), the CES proposal notifier and the training-matrix
    notifier would all have bypassed preferences entirely.
- **`src/api/routes/notifications.py`:** `category_preferences` routed through
  `merge_category_preferences` instead of `setattr`. The response now reports
  the **merged** state of `category_preferences` rather than echoing only what
  the caller sent, so a client cannot mistake its own payload for the stored
  truth.
- **`src/api/routes/push_notifications.py`:** its hand-rolled
  `existing.update(cat_updates)` replaced by the same shared helper. Behaviour
  is equivalent for flat flags and now additionally channel-merges nested
  entries. One rule, two callers.
- **`src/core/config.py`:** one new setting,
  `notification_quiet_hours_timezone: str = "Europe/London"` (env
  `NOTIFICATION_QUIET_HOURS_TIMEZONE`). Reason in §3.
- **Frontend:** `en.json` / `cy.json` — one string each.
  `notifications.pref.high_priority_alerts_desc` said "Receive alerts for
  critical and high priority items". Critical alerts (SOS, RIDDOR) deliberately
  **cannot** be muted, so the old copy promised a control the code must not
  honour. Now: "Receive alerts for high priority items. Critical safety alerts
  are always delivered." Keys unchanged, parity preserved. No component, page,
  nav or client file touched.
- **APIs:** No path, parameter, request body or response schema changed. The
  only OpenAPI difference is the `description` text of the two PUT operations
  (their docstrings). Verified by diffing `app.openapi()` against
  `openapi-baseline.json`: `differing operation fields: ['description']` for
  both, and zero notification paths added or removed.
- **Database:** **None.** No alembic revision. No column added, dropped,
  renamed or re-typed. No backfill, no data migration.
- **Tests:** NEW `tests/unit/test_notification_preference_enforcement.py`
  (56 tests); `tests/unit/test_notifications_routes.py` +4 tests. Detail in §5.
- **Docs:** This Change Ledger.
- **Dependencies:** None. `zoneinfo` is stdlib (Python 3.11 is already the
  floor — `tests/conftest.py` hard-fails below it).

## 3) Compatibility & Data Safety

- **A user who has never saved preferences sees no change.** Absent keys mean
  "no opinion", never "off". `filter_channels` with an empty snapshot returns
  the requested channels untouched. This is locked by
  `test_user_without_stored_preferences_keeps_previous_behaviour` and
  `test_no_stored_preferences_suppresses_nothing` — both pass identically on
  `origin/main` and on this branch, which is exactly what makes them useful as
  regression guards rather than bite tests.
- **Critical alerts can never be muted.** `filter_channels` returns early for
  `NotificationPriority.CRITICAL`, before both gates. `send_sos_alert` and
  `send_riddor_alert` are `CRITICAL`, so no category toggle and no quiet-hours
  window can suppress a lone-worker SOS or a RIDDOR alert. Two tests assert
  this, one with every channel explicitly disabled *and* quiet hours active.
- **No notification is ever lost, only channels are.** The `notifications` row
  is always inserted regardless of suppression, so a suppressed message still
  appears in the bell and in `GET /api/v1/notifications/`. Suppression removes
  the interruption, not the record.
- **Merge rule, stated precisely** (`merge_category_preferences`):
  - stored keys absent from the update survive it — this is the clobber fix;
  - a key present in the update replaces the stored value for that key;
  - when both stored and incoming values are channel maps, channels merge
    individually, so `{"push": false}` cannot drop a stored `email` opinion;
  - a shape change on one key (nested map → bare boolean) takes the explicit
    write, because it is an explicit write to that one key;
  - a non-mapping update (`null`, a string, `0`) is treated as **no change** —
    no caller has a legitimate reason to blank every other surface's settings,
    and the previous code would have persisted `None` over the lot;
  - a fresh dict is always returned, never the stored dict mutated in place,
    which is what makes SQLAlchemy notice the change on a plain `JSON` column
    (asserted by `test_result_does_not_alias_stored_dicts`).
  - **Consequence, stated plainly:** merge semantics mean a category key cannot
    be *deleted* through either PUT, only overwritten. The vocabulary is fixed
    and small, no client attempts deletion, and #1707 already established that
    a stale key in the JSON is ignored rather than rendered. Deletion, if ever
    needed, wants an explicit DELETE, not a silently destructive PUT.
- **Quiet hours are evaluated in a deployment-wide timezone, not the user's.**
  There is no timezone column on `notification_preferences` (nor on `users`) and
  the brief forbids a migration, so bounds are interpreted in
  `NOTIFICATION_QUIET_HOURS_TIMEZONE`, default `Europe/London`. For a UK
  platform this is right far more often than UTC would be — and it is correct
  through BST, which UTC is not. **It is wrong for a user in another timezone,
  and that is a schema limitation, not a solved problem.** Per-user quiet hours
  need a column and therefore a migration; I stopped rather than land one.
  Tested: 21:30 UTC in July is 22:30 in London and is treated as quiet, while
  the same instant in UTC is not.
- **Quiet hours hold back push and SMS only; in-app and email still go.**
  In-app is passive, and email is pull-based. Suppressing email would silently
  drop the only durable off-platform record, because the `email_digest_*`
  columns have no digest queue behind them to defer it to (#1707 removed the
  weekly-digest UI for exactly that reason). Deferring email properly needs that
  queue; that is a follow-up, not something to fake by dropping mail.
- **A mis-saved quiet-hours window cannot mute a user around the clock.**
  Equal bounds (`22:00`–`22:00`) describe no window rather than a whole day, and
  unparseable or missing bounds disable gating entirely with a debug log. Both
  are tested.
- **Bare booleans from the push API suppress push only.** The push route governs
  push; widening a `false` written there to email or SMS would enforce an intent
  the user never expressed. Documented in the module docstring and tested.
- **Malformed stored values degrade to "no opinion", not to silence.** A string
  where a channel map was expected, or `{"email": "true"}`, suppresses nothing.
  Tested.
- **Known no-op left in place, on purpose:** the `document_updates` category has
  no `NotificationType` behind it — no notification type models a document
  event, and document-campaign notifications are inserted directly rather than
  dispatched. The toggle therefore still gates nothing. Deleting the row is a UI
  change this PR is scoped out of, and faking a mapping would be worse. Recorded
  in a comment in `CATEGORY_BY_TYPE` and flagged here as follow-up.
- **Paths that bypass the canonical dispatcher are still unenforced**, and this
  PR does not claim otherwise: `compliance_schedule_notification_tasks.py`,
  `standards_assessment_notifications.py` and `document_campaign_service.py`
  each construct `Notification` rows directly and send email on their own.
  Routing them through `NotificationService` is the natural next KILL step; it
  is a behaviour change across three modules and does not belong in this PR.
- **Performance:** the preference query now also runs on the explicit-`channels`
  path, which previously skipped it — one indexed lookup on
  `notification_preferences.user_id` (unique) per notification. `create_bulk_
  notifications` already performed one insert and one commit per user, so this
  does not change its order of cost.
- **Breaking changes:** none for any API consumer. For users, delivery now
  narrows for anyone who had already opted out or configured quiet hours —
  which is the point of the change, and is why the copy fix in §2 ships with it.
- **Migration plan:** N/A — no schema change.
- **Rollback strategy (DB):** no DB change; revert the merge commit. Stored
  `category_preferences` and quiet-hours values remain valid either way, since
  the previous code simply ignored them.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Per-category channel toggles | Persisted to `category_preferences`, read by no delivery code | Enforced on every `create_notification`, per channel |
| Quiet hours | Three columns, editable on two APIs, compared to the clock nowhere | Push and SMS held back inside the window; in-app and email unaffected |
| Explicit `channels=` callers | Bypassed preferences entirely (`create_status`, CS assignment notifier, CES, training matrix) | Gated on the same rules; explicit channels state suitability, not consent |
| Critical safety alerts | Always delivered (no prefs consulted at all) | Always delivered, now by an explicit early return with two tests on it |
| `PUT /notifications/preferences` | Replaced `category_preferences` wholesale, deleting push-route keys | Key-wise merge; stored keys the payload cannot express survive |
| `PUT /notifications/push/preferences` | Hand-rolled merge, no channel-level merge | Same shared helper as the other surface — one rule, two callers |
| Partial category payload | Would drop untouched channels for that category | Channels merge individually |
| `category_preferences: null` | Persisted `None`, wiping both surfaces' settings | Treated as no change |
| PUT response body | Echoed the caller's own payload | Reports the merged stored state |
| Suppression visibility | Nothing to see; delivery just did not respect prefs | `extra_data.suppressed_channels` records channel → reason, plus one INFO log |
| Quiet-hours timezone | N/A (never evaluated) | `Europe/London` by default, overridable by env; per-user TZ honestly declared as needing a migration |
| `high_priority_alerts` copy | Promised control over "critical and high priority items" | States that critical safety alerts are always delivered |
| Alembic heads | 1 | 1 — no revision added |
| Tests on prefs enforcement | None (`category_preferences` had one persistence test) | 63 tests across the two files, 5 proven to fail without the change |

## 4) Acceptance Criteria (AC)

- [x] AC-01: A user with `{"audit_notifications": {"email": false}}` stored
  receives no email for an audit notification, while in-app and push still fire.
- [x] AC-02: Enforcement applies when the caller passed explicit `channels=`,
  not only on the preference-derived path.
- [x] AC-03: Inside a user's quiet-hours window, push and SMS are not
  dispatched; in-app and email are, and the notification row still exists.
- [x] AC-04: A quiet-hours window spanning midnight (22:00–07:00) is treated as
  quiet at 23:30 and at 02:00, and not quiet at 12:00.
- [x] AC-05: `CRITICAL` notifications (SOS, RIDDOR) deliver on every requested
  channel even with every category disabled and quiet hours active.
- [x] AC-06: A user with no stored preferences receives exactly what they
  received before this PR.
- [x] AC-07: `PUT /api/v1/notifications/preferences` with the full five-category
  map preserves `incident_alerts` / `mentions` written by the push route.
- [x] AC-08: `PUT /api/v1/notifications/push/preferences` preserves nested
  channel maps written by the main route.
- [x] AC-09: A partial category payload (`{"action_reminders": {"push": false}}`)
  leaves the other channels of that category intact.
- [x] AC-10: No alembic revision is added; `alembic heads` reports the single
  head `20261104_lib_cut1b_drop`, and `git diff` shows zero changes under
  `alembic/`.
- [x] AC-11: No `Layout.tsx`, nav, Audit Builder, dashboard Recent-cases or
  admin Notifications file is touched; no N1 inventory UI or N2 flag work.
- [x] AC-12: No API path, parameter or response schema changes; the OpenAPI
  compatibility check passes.
- [x] AC-13: No existing test was skipped, loosened, renamed or deleted to go
  green.
- [x] AC-14: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

Run locally in `.worktrees/notif-admin-03-prefs` with
`/Users/davidharris/quality-governance-platform/.venv/bin/python` (3.11.15):

- [x] **Full backend unit suite** `pytest tests/unit -q` → **6,564 passed, 0
  failed, 11 skipped** in 146s. The 11 skips are pre-existing and unrelated (the
  one in the notification neighbourhood is
  `test_retention_rules_are_answerable.py:46`, "notification_logs is
  operational, not governed by a retention policy" — it skips identically on
  `origin/main`).
- [x] `pytest tests/unit/test_notification_preference_enforcement.py
  tests/unit/test_notifications_routes.py -q` → **63 passed, none skipped**.
- [x] Notification neighbourhood
  (`-k "notif or push or mention or assignment or workforce or sms or capa"`) →
  **503 passed, 1 skipped** (the retention skip above).
- [x] `mypy src/ --config-file pyproject.toml` → **Success: no issues found in
  602 source files**.
- [x] `black --check src/ tests/` → 1,410 files unchanged;
  `isort --check-only --settings-path pyproject.toml src/ tests/` → clean;
  `flake8 src/ tests/` → clean.
- [x] `scripts/validate_type_ignores.py` → passed (216/216; the 190 untagged
  ignores are pre-existing and non-blocking, none added here).
- [x] `scripts/check_mock_data.py --repo-root .` → `[PASS] No mock data patterns
  detected`.
- [x] `scripts/check_openapi_compatibility.py openapi-baseline.json <generated>`
  → **Contract check PASSED**, no breaking changes. Additionally diffed the two
  PUT operations against the baseline directly: the only differing operation
  field is `description`, and no notification path was added or removed.
- [x] **New tests proven to bite (each revert reverted afterwards):**
  - `git checkout origin/main -- src/api/routes/notifications.py
    src/api/routes/push_notifications.py` → exactly the two clobber tests fail
    (`test_update_preferences_merges_instead_of_clobbering_push_keys`,
    `test_update_preferences_partial_category_payload_keeps_other_channels`);
    **2 failed, 5 passed**.
  - `git checkout origin/main -- src/domain/services/notification_service.py` →
    exactly the three dispatcher tests fail
    (`test_category_opt_out_stops_email_delivery`,
    `test_explicitly_requested_channels_are_still_gated`,
    `test_quiet_hours_stop_push_and_sms_but_keep_the_in_app_record`);
    **3 failed, 53 passed**.
- [x] Coverage of the pure rules: category mapping (4), category suppression
  (9 incl. malformed values), quiet-hours window arithmetic (parsing 12,
  windows 4), quiet-hours evaluation (8 incl. BST and unknown-timezone
  fallback), channel gating (3), dispatcher behaviour (5), merge semantics (10).

**Stated honestly — tests that are guards, not bite tests:** the two
"unchanged behaviour" tests (AC-06) and the push-route merge test (AC-08) pass on
`origin/main` too. The push route already merged flat flags; that test exists to
freeze the behaviour now that it runs through the shared helper, and to catch the
reverse-direction clobber if the helper ever regresses. Claiming them as proof of
new behaviour would be false.

**Not verified:** no frontend test or lint run — `frontend/node_modules` is not
installed in this worktree, and the only frontend change is two locale string
values with unchanged keys (both files re-parsed as valid JSON: 4,228 / 3,894
keys, unchanged counts). No integration or smoke test was run: the enforcement
tests exercise the service with a stubbed session, so **no evidence here comes
from a real database or a real WebSocket/Celery delivery**. No browser was
driven. Quiet hours were tested with a frozen clock, not by waiting for 23:30.

- [ ] Full CI — on PR.
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge).

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: User opens Notifications → Preferences, turns off email for Audit
  Notifications, saves; a later audit-completion notification arrives in-app but
  sends no email. (Unit-level: stubbed session, delivery methods asserted.)
- [x] CUJ-02: User sets quiet hours 22:00–07:00; an overdue-action notification
  at 23:30 London writes the row and emails, and does not push or SMS.
- [x] CUJ-03: A lone worker triggers SOS during that same window with every
  category switched off — all four channels still dispatch.
- [x] CUJ-04: A user who has saved preferences through the push API then saves
  the Notifications page; their `incident_alerts` and `mentions` flags survive.
- [ ] CUJ-05: The same four journeys against real tenant data with a live
  Postgres, Celery and WebSocket — to verify on tip after deploy.

## 7) Observability & Ops

- **New signal:** when a preference holds a channel back, the notification row
  carries `extra_data.suppressed_channels` as `{channel: reason}` where reason is
  `category:<id>` or `quiet_hours`, and one INFO line is logged with user id,
  notification type and the same map. That makes "why did I not get emailed?"
  answerable from the row itself instead of by re-deriving preferences.
- **No message content is logged** — user id, type and channel reasons only.
- **New config:** `NOTIFICATION_QUIET_HOURS_TIMEZONE` (default `Europe/London`).
  An unknown zone name logs a WARNING and falls back to UTC rather than raising;
  a failure reading settings at all falls back to the module default and logs at
  debug, because a config read must not break dispatch.
- **Metrics / alerts:** none added. If suppression volume needs watching, the
  INFO log is the hook to count on; no dashboard is claimed here.
- **Runbook:** no operational procedure changes. Support answering "I stopped
  getting emails" should check `category_preferences` and quiet hours first —
  those settings now have an effect, which was not previously true.

## 8) Release Plan

1. Open PR on tip `5cd4a43fb` (#1707 merged). **Do not merge** — raised for
   review only, per the request.
2. Merge only after the ledger / compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark FR-NOTIF-ADMIN-03 conveyor **PROD → DONE**. Merge alone is not
   done.

## 9) Rollback Plan

- **Trigger:** users report missing notifications they expected, i.e. the
  category mapping suppresses more than intended, or quiet hours fire outside
  the intended window for a non-UK user.
- **Rollback steps:** revert the merge commit and let the pipeline deploy the
  reverted tip. No schema change, no data migration, no flag to flip, so the
  revert is complete on its own — stored `category_preferences` and quiet-hours
  values stay valid and simply become inert again.
- **Partial mitigation without a revert:** a user's own quiet hours can be
  disabled through either preferences API, and
  `NOTIFICATION_QUIET_HOURS_TIMEZONE` can be repointed by env var without a
  code change.
- **Owner:** Platform Engineering (Governance UX lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/notif-admin-03-prefs`
- Base: `5cd4a43fb` (#1707, which includes #1704 KILL-1)
- Files: 9 changed — 1 new domain module, 1 dispatcher, 2 routes, 1 config,
  2 locale strings, 1 new test file, 1 extended test file, plus this ledger
- Alembic revisions added: **0**. `alembic heads` → single head
  `20261104_lib_cut1b_drop`; `git diff HEAD -- alembic/` is empty.
- Local evidence: 6,564 backend unit tests green; mypy clean over 602 files;
  black / isort / flake8 clean; OpenAPI contract check passed; 5 new tests proven
  to fail without their change (see §5)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — no path, parameter, request or response schema
  change; only two operation `description` strings differ from
  `openapi-baseline.json`; compatibility check passes; no alembic revision, no
  column change, no new table
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A. No flag: this makes already-stored consent
  effective, and gating that would keep the dishonest default
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] No `Layout.tsx` and no nav edit of any kind
- [x] No Audit Builder / `AuditTemplateBuilder` / `audit-builder` edits
- [x] No `RecentCasesPanel.tsx` or dashboard edits (no overlap with #1706)
- [x] No `admin/NotificationSettings.tsx` edit — the cosmetic cards deleted in
  #1707 are not resurrected
- [x] No alembic revision; no second head. Every enforced field already exists
  on `notification_preferences`
- [x] No new settings table — `NotificationPreference` is the store, as briefed
- [x] No N1 notification inventory UI and no N2 feature-flag work
- [x] No test skipped, loosened, renamed or deleted to go green
- [x] Frontend change is two locale **values**; no key added or removed, no
  component, page or API client touched
- [x] `notification_service` is the only dispatcher edited, and it is edited to
  finish what #1704 KILL-1 started rather than to add a parallel path
