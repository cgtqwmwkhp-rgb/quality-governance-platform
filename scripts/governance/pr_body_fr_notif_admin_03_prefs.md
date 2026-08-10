# Change Ledger (CL-FR-NOTIF-ADMIN-03)

> Base: `origin/main` @ `5cd4a43fb` (#1707 honesty sweep, LIVE).
> Backend + two i18n strings — no alembic, no API contract change, no new flag.

## 1) Summary

- **Feature / Change name:** FR-NOTIF-ADMIN-03 — notification category
  preferences and quiet hours actually gate delivery, and the two preference
  write surfaces stop overwriting each other
- **User goal (1–2 lines):** When a user turns off email for a category, the
  email stops arriving. When a user has quiet hours set, their phone stops
  buzzing overnight. Saving preferences on one screen does not silently wipe
  what they saved on the other.
- **Problem:** Two independent faults, both invisible until you look.
  1. `NotificationPreference.category_preferences`, `quiet_hours_enabled`,
     `quiet_hours_start` and `quiet_hours_end` were **stored and read back to
     the UI but never consulted by any delivery path**. `_get_delivery_channels`
     looked only at the three top-level `*_enabled` booleans. Every per-category
     toggle in the Notifications settings tab was decorative, and quiet hours
     had no enforcement site anywhere in `src/`.
  2. `PUT /api/v1/notifications/preferences` and
     `PUT /api/v1/notifications/push/preferences` both write the single
     `category_preferences` JSON column with **different key namespaces**. The
     canonical route did a wholesale replace. The user-facing tab only knows the
     five `CATEGORY_IDS`, so every save silently deleted `incident_alerts`,
     `compliance_updates` and `mentions` — keys the push surface owns and this
     surface cannot even display.
- **In scope:**
  - NEW `src/domain/services/notification_preferences.py` — one pure,
    database-free module holding category mapping, channel-opinion reading,
    quiet-hours evaluation and merge semantics
  - `NotificationService.create_notification` resolves channels through that
    module, so preferences bind on the canonical dispatcher
  - Suppression audit trail written into `extra_data["suppressed_channels"]`
  - Merge-not-clobber on both preference write surfaces, via one shared helper
  - `notification_quiet_hours_timezone` setting (default `Europe/London`)
  - Two i18n strings corrected to stop over-promising (en + cy)
- **Out of scope / deferred:**
  - A quiet-hours UI. No frontend control writes `quiet_hours_enabled` today
    (see §3) — this PR makes the stored value load-bearing, it does not add the
    control that sets it.
  - Making the `document_updates` toggle real. No `NotificationType` models a
    document event, so there is nothing to gate (see §3).
  - Per-user timezones for quiet hours. There is no column for one.
  - A digest queue to defer email suppressed overnight.
- **Feature flag / kill switch:** None — rollback is revert. Deliberate: a flag
  would mean shipping a preference system that may or may not be listening,
  which is the fault being fixed.

## 2) Impact Map (what changed)

- **Backend:**
  - NEW `src/domain/services/notification_preferences.py` (358 lines) —
    `CATEGORY_BY_TYPE`, `categories_for`, `is_channel_muted`, `parse_hhmm`,
    `in_quiet_window`, `is_quiet_hours`, `filter_channels`,
    `merge_category_preferences`, plus `PreferenceSnapshot` / `ChannelDecision`.
    No database access, so it is exhaustively testable and both routes and the
    dispatcher share exactly one definition of the rules.
  - `src/domain/services/notification_service.py` — `create_notification` calls
    the new `_resolve_delivery_channels` **before** constructing the row, so the
    suppression record is present at insert. `_get_delivery_channels` split into
    `_load_preferences` + `_channels_from_toggles` and retained as a thin
    wrapper (existing callers and tests unchanged).
  - `src/api/routes/notifications.py` — `category_preferences` merged, not
    replaced; the response now reports merged state rather than echoing the
    request.
  - `src/api/routes/push_notifications.py` — its hand-rolled merge replaced by
    the shared helper, so both surfaces cannot drift apart again.
  - `src/core/config.py` — `notification_quiet_hours_timezone`.
- **Frontend:** two i18n values only (`en.json`, `cy.json`). No component,
  no route, **no `Layout.tsx` or navigation shell edit**.
- **APIs:** No contract change. Same paths, same request schemas, same status
  codes. `PUT /api/v1/notifications/preferences` returns a strictly richer
  `preferences.category_preferences` (merged state); no field was removed.
- **Database:** None. No alembic revision. Every column read already exists.
- **Tests:** NEW `tests/unit/test_notification_preference_enforcement.py`
  (56 tests); `tests/unit/test_notifications_routes.py` extended (+4).
- **Docs:** This Change Ledger.

## 3) Compatibility & Data Safety

- **Absent means "no opinion", never "off".** A user with no stored preferences,
  or a category key that was never written, keeps exactly the delivery they had
  before this PR. `test_user_without_stored_preferences_keeps_previous_behaviour`
  is the regression guard. This is the single most important compatibility
  property here: the failure mode of getting it wrong is mass silent muting.
- **Two stored value shapes, both honoured.** The user-facing tab writes
  `{"email": bool, "push": bool, "in_app": bool}`; the push API writes bare
  booleans. A bare `false` suppresses **push only**, because that route governs
  no other channel — widening it to email/SMS would enforce an intent the user
  never expressed. Malformed or unknown shapes degrade to "no opinion" rather
  than raising mid-dispatch.
- **CRITICAL bypasses both gates.** `SOS_ALERT` and `RIDDOR_INCIDENT` cannot be
  muted by any toggle or quiet-hours window. Asserted twice.
- **Quiet hours hold back push and SMS only.** In-app is passive and email is
  pull-based; suppressing email would drop the only durable off-platform record,
  and there is no digest queue to defer it to. Suppressing `in_app` (possible
  via an explicit category toggle) skips the live WebSocket nudge only — the row
  is still inserted and still appears in the list on next fetch.
- **Equal quiet-hours bounds describe no window,** so a mis-saved `22:00`/`22:00`
  cannot mute a user around the clock. Unparseable bounds do not gate at all.
- **Timezone:** bounds are bare `HH:MM` with no per-user timezone column, so
  they are interpreted in a deployment-wide setting rather than pretending to be
  per-user. An unknown zone name falls back to UTC with a warning instead of
  raising.
- **Merge is key-wise, and channel-wise when both sides are maps,** so a partial
  payload cannot drop a channel the user never touched. A non-mapping update
  (`None`, a string) is treated as "no change" — no caller has a legitimate
  reason to blank every other surface's settings. The helper returns a fresh
  dict, which is what makes SQLAlchemy notice the JSON column changed.
- **Breaking changes:** None to any contract. One intended behaviour change,
  stated plainly below.
- **Migration plan:** N/A.
- **Rollback strategy:** Revert the merge commit. No schema, no flag, no data
  written that a revert would strand.

### Intended behaviour change (blast radius, measured not guessed)

Explicitly-requested `channels=[...]` are now gated too. A caller passes
channels to say what a message *suits*, not to assert the user consented to be
interrupted. Three call sites pass explicit channels:

| Call site | Type / priority | Effect |
| --- | --- | --- |
| `notification_service.notify_status_change` | `ACTION_COMPLETED` / MEDIUM, in-app only | None — uncategorised type, and quiet hours do not gate in-app |
| `ces_asset_import_service` (safety lookups) | `APPROVAL_REQUESTED` / **HIGH**, in-app + email | Email now suppressed **iff** the user set `high_priority_alerts.email = false` |
| `api/routes/training_matrix` (frequency change) | `APPROVAL_REQUESTED` / **HIGH**, in-app + email | Same |

That is the toggle doing what its label promises. Users who never opened the
settings tab have no stored key and are unaffected; users who saved it with the
shipped defaults have `high_priority_alerts.email = true` and are also
unaffected.

### Known gaps — stated, not silently papered over

- **No UI enables quiet hours.** `quiet_hours_enabled` is accepted by
  `PUT /api/v1/notifications/preferences` and is now enforced, but no frontend
  control writes it; `notificationsClient.ts` declares the fields and nothing
  sends them. Enforcement is the prerequisite for that control, not a
  substitute for it. **This PR does not claim user-facing quiet hours work.**
- **The push API writes `quiet_hours_start`/`quiet_hours_end` but never
  `quiet_hours_enabled`,** so bounds set through that surface stay dormant. Not
  auto-enabled here on purpose: inferring consent from two bounds would switch
  on suppression for anyone who ever set them, which is the opposite of the
  "absent means no opinion" rule this PR is built on.
- **The `document_updates` toggle still does nothing.** No `NotificationType`
  models a document event, and document campaign notifications are inserted
  directly rather than dispatched through `NotificationService`. Making it real
  means routing those inserts through the service first. Recorded in the module
  docstring as follow-up rather than faked with a mapping that never fires.
  Four of the five user-facing categories are now live; this one is not.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Category preference enforcement | Stored, echoed to UI, **never read by any delivery path** — five decorative toggles | Read on every `create_notification`; four of five categories genuinely gate email/push/SMS/in-app |
| Quiet hours enforcement | `quiet_hours_*` columns existed with **zero enforcement sites in `src/`** | Enforced on the canonical dispatcher for push and SMS; UI control still absent and declared as such |
| Life-safety override | No gate existed, so nothing could mute an SOS — safe by accident | Safe by construction: CRITICAL bypasses both gates, asserted by test |
| Cross-surface preference writes | Canonical route replaced `category_preferences` wholesale, silently deleting the push API's `incident_alerts` / `compliance_updates` / `mentions` | Both surfaces merge through one shared helper; neither can delete keys it cannot display |
| Update semantics drift | Two routes, two hand-rolled behaviours, no shared definition | One `merge_category_preferences`; divergence now requires deleting a test |
| Suppression auditability | N/A — nothing was suppressed | Every suppression records channel and reason (`category:<id>` or `quiet_hours`) in `extra_data`, written at insert so no post-hoc JSON mutation is relied on |
| Response honesty (`PUT` prefs) | Echoed the caller's own payload back, so a client could not see merged state | Returns the persisted merged `category_preferences` |
| Copy honesty | "Receive alerts for critical and high priority items" — implied the toggle could mute critical alerts | "Critical safety alerts are always delivered" — matches the CRITICAL bypass (en + cy) |
| Timezone honesty | — | Deployment-wide setting, documented as not per-user, rather than implying per-user quiet hours |

## 4) Acceptance Criteria (AC)

- [x] AC-01: A category opt-out stops that channel on the canonical dispatcher —
  `assignment_notifications.email = false` means `_deliver_email` is never
  awaited, while in-app and push still are.
- [x] AC-02: Quiet hours suppress push and SMS but keep in-app and email; the
  window is evaluated in the configured timezone and handles the
  across-midnight case (23:30 UTC in July = 00:30 London → quiet).
- [x] AC-03: CRITICAL bypasses everything — an `SOS_ALERT` during quiet hours
  with `incident_alerts` switched off still delivers push and SMS, and records
  no suppression.
- [x] AC-04: `PUT /api/v1/notifications/preferences` cannot delete keys it does
  not display — `incident_alerts` and `mentions` survive a save from the
  settings tab, and the response reports the merged state.
- [x] AC-05: The reverse direction holds too — the push API's flat flags do not
  drop the tab's nested channel maps.
- [x] AC-06: A partial channel map (`{"push": false}`) leaves `email` and
  `in_app` untouched rather than dropping them.
- [x] AC-07: A user with no stored preferences receives exactly what they
  received before this change; nothing is suppressed.
- [x] AC-08: Every suppression is auditable — `extra_data["suppressed_channels"]`
  names the channel and whether a category or quiet hours caused it.
- [x] AC-09: Malformed stored data cannot break dispatch — a string entry, a
  non-boolean channel value, and unparseable `HH:MM` bounds all degrade to "no
  opinion".
- [x] AC-10: Change Ledger body present for the ledger gate / checklist.
- [ ] AC-11: Quiet-hours UI control writing `quiet_hours_enabled` — **deferred**,
  not delivered here (see §3).
- [ ] AC-12: `document_updates` toggle made real — **deferred**, requires
  routing document campaign inserts through `NotificationService` (see §3).

## 5) Testing Evidence

Run locally in the worktree, base `5cd4a43fb`:

- [x] `pytest tests/unit/test_notification_preference_enforcement.py
  tests/unit/test_notifications_routes.py` → **63 passed, 0 skipped**
- [x] Regression sweep across the notification surface —
  `test_notification_service.py`, `test_action_assignment_notify.py`,
  `test_workforce_notifications.py`,
  `test_standards_assessment_notifications.py`,
  `test_compliance_schedule_notifications.py`,
  `test_compliance_schedule_assignment_notify.py`,
  `test_document_campaign_overdue_notifications.py`,
  `test_c67_push_migration_adoption.py`, `test_audit_capa_closure_bridge.py`
  → **123 passed, 0 skipped**
- [x] `black --check` → clean (7 files)
- [x] `isort --check-only --settings-path pyproject.toml` → clean
- [x] `flake8 --count` → **0**
- [x] `mypy src/ --config-file pyproject.toml` → **Success: no issues found in
  602 source files**
- [x] `scripts/validate_type_ignores.py` → passed
- [x] `scripts/check_mock_data.py --repo-root .` → `[PASS]`
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

**Not verified.** Frontend tests were not run: `frontend/node_modules` is not
installed in this worktree. The frontend change is two i18n *values* — no key
added or removed, so locale-parity checks are unaffected — and a repo-wide grep
found no test asserting the old English copy. That is reasoning, not a green
run, and CI is the actual check. Also not verified: behaviour against a real
Postgres row or a live WebSocket/APNs path; enforcement is proven against the
dispatcher with mocked delivery methods and a mocked session.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: A user turns off email for assignments and is still notified
  in-app and by push — the opt-out is precise, not a blanket mute.
- [x] CUJ-02: A user with quiet hours 22:00–07:00 gets an overdue-action email
  and in-app record at 23:30 but no push and no SMS; the suppression reason is
  recorded as `quiet_hours`.
- [x] CUJ-03: A lone worker triggers an SOS at 23:30 with quiet hours on and
  incident alerts off — push and SMS both deliver.
- [x] CUJ-04: A user saves the Notifications settings tab; their previously
  stored `incident_alerts` and `mentions` push preferences survive.
- [x] CUJ-05: A user who has never opened notification settings sees no change
  in what they receive.
- [ ] CUJ-06: End-to-end quiet hours from the UI — **cannot be exercised**; no
  UI writes `quiet_hours_enabled` yet (§3).

## 7) Observability & Ops

- **Logs:** one `INFO` per notification that had any channel suppressed, naming
  user, notification type and the channel→reason map. Silent suppression would
  make this feature undebuggable in production, which is how the original
  toggles stayed decorative for so long.
- **Per-notification audit:** `extra_data["suppressed_channels"]` on the row
  itself, so "why did I not get this?" is answerable from the database without
  correlating logs.
- **New setting:** `notification_quiet_hours_timezone` (default
  `Europe/London`). An unknown value logs a warning and falls back to UTC rather
  than failing dispatch.
- **Metrics:** none new.
- **Ops note:** if support reports missing notifications after this ships, the
  first query is `extra_data->>'suppressed_channels'` on the affected rows —
  that distinguishes "preference honoured" from "delivery broken".

## 8) Release Plan

1. Open PR on tip `5cd4a43fb` (#1707 LIVE). **Do not merge** — review requested.
2. Merge only after the ledger/compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains that SHA on the prod FQDN.
4. Only then mark FR-NOTIF-ADMIN-03 conveyor **PROD → DONE**. Merge alone is not
   done.
5. Follow-on: AC-11 (quiet-hours UI) and AC-12 (`document_updates`).

## 9) Rollback Plan

- **Trigger:** Users report notifications going missing that they did not opt
  out of; or `extra_data.suppressed_channels` shows suppressions for users with
  no stored preferences; or dispatch latency regresses from the extra
  preference read.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline
  deploy the reverted tip. No schema change, no flag, no migration, so the
  revert is complete on its own — the preference columns simply return to being
  unread, which is the pre-PR behaviour. No data repair needed; nothing written
  by this PR is destructive, and the merge semantics only ever preserve more
  data than before. `Emergency Rollback - Production` can restore the previous
  container image first if the backend needs to move faster than a revert
  deploy.
- **Owner:** Platform Engineering (Notifications lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/notif-admin-03-prefs`
- Base: `5cd4a43fb` (#1707, PROD LIVE)
- Files: 9 changed (+1200 / −37); 2 new
- New module: `src/domain/services/notification_preferences.py` (358 lines,
  no database access)
- Local evidence: 63 + 123 pytest green; black / isort / flake8 / mypy clean;
  type-ignore and mock-data gates pass (see §5)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — no API contract change, no schema, no alembic
  revision; response payload strictly additive
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A (no flag; behavioural fix guarded by the
  no-stored-preferences regression test)
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] No `Layout.tsx` / navigation shell edits
- [x] No alembic revision; no model column added, removed or retyped
- [x] No API route, request schema or status-code change
- [x] Frontend touched only in two i18n values — no component, no client, no
  test file
- [x] Builds on #1707's honesty sweep rather than reversing it: that PR deleted
  controls nothing implemented, this PR implements the ones worth keeping and
  names the two that are still not real
- [x] `_get_delivery_channels` retained as a wrapper, so existing callers and
  `test_notification_service.py` need no edits
