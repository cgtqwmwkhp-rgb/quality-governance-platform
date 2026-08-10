# Change Ledger (CL-FR-NOTIF-ADMIN-01)

> Base: `origin/main` @ `80d88bcc5` (#1709 FR-WFFORCE-CAL-01 / FR-WF-CG-01).
> A new read-only surface and the registry behind it. **No alembic revision, no
> column, no dispatcher edit.** Deliberately disjoint from #1710 ADMIN-03, which
> is still open and owns the delivery path.

## 1) Summary

- **Feature / Change name:** FR-NOTIF-ADMIN-01 — an honest inventory of what this
  deployment can actually notify
- **User goal (1–2 lines):** An administrator opening `/admin/notifications`
  should be able to answer "does this platform send email?", "what actually
  triggers a notification?" and "is anything wired up but dead?" without reading
  the source. Until this PR the page could not answer any of the three.
- **Problem:** FR-HONESTY-SWEEP-01 (#1707) deleted four channel cards —
  Email, SMS, Push, Webhook Integration — whose switches wrote to `useState`
  and nothing else. That removed the lie and left the question unanswered. Worse,
  the deletion is itself misleading in one direction: an administrator who had
  been shown a "Webhook Integration" card now simply sees nothing, and an absence
  does not correct a belief. Meanwhile four `NotificationService` helpers —
  `send_sos_alert`, `send_riddor_alert`, `notify_competency_expiry` and
  `process_mentions` — are fully written, fully tested, and called by nothing in
  production. A lone worker raising an SOS in this product notifies nobody. That
  fact was discoverable only by grepping for callers.
- **In scope:**
  - New pure registry `src/domain/notifications/inventory.py`: the 4 delivery
    channels the dispatcher really branches on, the 2 channels people expect and
    this product does not have, and all 22 notification producers — 18 live and
    4 that no production path reaches
  - New read-only endpoint `GET /api/v1/notifications/inventory`, gated on the
    existing `admin:manage` permission
  - A read-only panel on `admin/NotificationSettings` that renders it, adding no
    control of any kind
  - Tests: 74 new backend/integration tests, +9 frontend
- **Out of scope / deliberately not done:**
  - **No dispatcher edit.** `notification_service.py`,
    `routes/notifications.py` and `routes/push_notifications.py` are untouched —
    those are #1710 ADMIN-03's files and it is still open. See the anti-conflict
    checklist.
  - **No alembic revision, no column, no table.** Nothing here persists.
  - **The four dead producers are not wired up.** Giving `send_sos_alert` a
    caller is a safety-behaviour change that deserves its own PR and its own
    review; this PR's job is to stop the deadness being invisible. Reporting it
    is not fixing it, and this ledger does not claim otherwise.
  - **The `notifications/{notification_id}` route-ordering hazard is recorded,
    not fixed** — see §3.
  - `Layout.tsx` / nav: untouched. No N2 feature-flag work. The Compliance
    Schedule toggles already on the page are left exactly as they are.
- **Feature flag / kill switch:** None. This adds a read behind an existing
  permission; there is no behaviour to stage and nothing to roll forward into.

## 2) Impact Map (what changed)

12 files, +2,598 / −20.

- **NEW `src/domain/notifications/inventory.py` (743 lines):** pure, no DB, no
  ORM, no `src.infrastructure` import.
  - `CHANNELS` — the 4 real channels (`in_app`, `email`, `sms`, `push`), each
    with the transport named concretely and the status helper that decides its
    readiness.
  - `ABSENT_CHANNELS` — `webhook` and `digest`, recorded rather than omitted, each
    saying where the nearby real feature lives (partner webhooks at
    `/admin/partner-webhooks`; no digest job exists at all).
  - `PRODUCERS` — 22 declarations, each naming module, symbol, channels, trigger,
    cadence, the Celery beat entry behind that cadence, gating feature flags, and
    whether anything outside the declaring module calls it.
  - `classify_readiness()` / `can_send()` — collapse a status helper's payload to
    one of five values. `READY` and `DEGRADED` can send; `NOT_CONFIGURED`,
    `DISABLED` and `NOT_IMPLEMENTED` cannot.
  - `build_inventory()` — assembly; every input is supplied by the caller, which
    is what lets the whole vocabulary be tested with no app and no database.
- **Why a written declaration rather than a runtime scan.** A registry computed by
  walking the import graph cannot disagree with the code, so a test comparing the
  two would pass whatever the code did — the vacuity `src/domain/authz/catalogue`
  already documents for the permission vocabulary. Writing the producers down
  means adding one is a reviewable diff, and
  `tests/unit/test_notification_inventory.py` holds the declaration to the tree:
  every `module`/`symbol` must resolve, every producer module found by grepping
  the source for notification creation must be declared, and a claimed cadence
  must be a task really present in `celery_app.conf.beat_schedule`. All three are
  proven to bite in §5.
- **NEW `src/api/routes/notification_inventory.py` (132 lines):** one `GET`.
  Mounted at `/notifications/inventory` from its own router rather than inside
  `routes/notifications.py`, so the reporting surface cannot acquire a dispatch
  side effect and so this lane does not edit a file ADMIN-03 owns.
  - Gated on `require_permission("admin:manage")` — an existing token, so the
    permission catalogue gains no vocabulary and the route census records no new
    debt. A superuser gate would have pushed `Posture.SUPERUSER` past the ceiling
    in `route_declarations.py`.
  - Each status helper is consulted in its own `try`, and a helper that raises is
    reported as absent. An inventory that 500s because one optional channel's
    environment is malformed tells an operator less than one that says the
    channel is not configured.
  - The VAPID public key is dropped from the payload before it is returned.
- **NEW `src/api/schemas/notification_inventory.py` (80 lines):** response models
  only. There is no request body and no update schema, because the endpoint
  reports rather than changes.
- **`src/api/__init__.py`:** +8 lines, mounting the new router. No existing
  include is reordered.
- **Frontend `admin/NotificationSettings.tsx`:** +226 lines — one read-only card
  listing channels with their readiness and the server's own explanation, and
  producers with module, symbol, cadence and flag state. Rendering only: no
  switch, no checkbox, no button, no write. The loader is a `useCallback` with an
  empty dependency list and stores its failure as a *kind* rather than a
  translated sentence, so it does not close over `t` — a loader whose identity
  changes per render re-runs on every render, which is a fetch loop rather than a
  fetch. There is a test for exactly that (§5).
- **Frontend i18n:** 17 new keys in **both** `en.json` and `cy.json`. Parity for
  the added keys is exact, verified by parsing both files.
- **APIs:** one path added, `GET /api/v1/notifications/inventory`. Nothing
  changed, nothing removed. Contract check passed.
- **Database:** **None.** No alembic revision; `git diff origin/main...HEAD --
  alembic/` is empty.
- **Dependencies:** none added.

## 3) Compatibility & Data Safety

- **Purely additive.** A new path, a new panel, and a new domain module imported
  by nothing that existed before. No caller of any existing function sees
  different behaviour. Reverting is a straight revert.
- **The endpoint is a reader, and that is asserted rather than asserted-about.**
  Three separate checks: the router itself may declare no method outside
  `{GET, HEAD}`; no route of *any* router mounts a write at that exact path; and
  reading leaves the `feature_flags` table byte-identical. The last one matters —
  `GET /api/v1/feature-flags/{key}` **seeds** the Compliance Schedule notify rows
  when they are missing, which is right for a page whose next action is a toggle
  and wrong for a report. Row identity is compared, not just row count, so an
  insert paired with a delete could not pass either.
- **An absent feature-flag row is reported as "default in force", not as "off".**
  These flags default to *on* when no row exists. Rendering them as off would
  invert the behaviour the operator is trying to understand, so `persisted` is
  carried all the way to the UI alongside `enabled`.
- **No key material and no secret values.** The VAPID helper returns the public
  key and the route drops it. The test sets sentinel values for both the public
  and the private key and greps the entire response body for them, rather than
  asserting on the field name the key would have arrived under — so re-adding it
  under any name fails. Presence booleans (`private_key_present`) are kept,
  because dropping the value must not cost the operator the fact.
- **Recorded, not fixed — `DELETE /api/v1/notifications/inventory` falls through
  to a pre-existing catch-all.** `DELETE /api/v1/notifications/{notification_id}`
  is declared in `routes/notifications.py` before this router is mounted, and
  `{notification_id}` is a single path segment, so it matches the literal
  `inventory` and answers instead of a 405. This is a **pre-existing property of
  the namespace** — the same is already true of the `preferences`,
  `unread-count` and `mentions` literals — and is not introduced here. It is not
  fixed in this PR because the fix is a re-ordering inside `notifications.py`,
  which is the file #1710 is concurrently changing. What is asserted instead is
  that the fall-through is inert: `notification_id` is typed `int`, so the path
  never resolves to a row, and the response is 403 or 422. **Follow-up owed.**
- **The report can be wrong in one direction, and the tests are what stop it.**
  A declaration is a human artefact; a producer added tomorrow could go
  undeclared. That is precisely what
  `test_every_producer_module_in_the_source_is_declared` prevents, by grepping
  the source for the ways a notification row is created and requiring every
  module it finds to appear in the registry. Proven to bite in §5. It is a grep,
  so a producer that creates notifications by a route none of its patterns match
  would still slip through; that residual risk is real and is stated rather than
  papered over.
- **Performance:** one request reads three environment-only status helpers and
  performs one `list_flags()` query. No N+1, no per-producer query.
- **Breaking changes:** none.
- **Migration plan:** N/A — no schema change.
- **Rollback strategy (DB):** N/A — nothing is written.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| "Does this deployment send email?" | Unanswerable from the UI after #1707 deleted the cards | Reported per channel with the server's readiness and its own explanation |
| Webhook channel | A deleted card, leaving the earlier belief uncorrected | Named as `not_implemented`, with partner webhooks pointed to as the real nearby feature |
| Email digest | Two unread columns on `notification_preferences` and no job | Declared absent; every email is stated to be per-event |
| SOS / RIDDOR / competency-expiry / @mention helpers | Written, tested, called by nothing; discoverable only by grepping | Declared `no_production_caller` and surfaced as "Notifies nobody" |
| New producer added later | Nothing would notice | `test_every_producer_module_in_the_source_is_declared` fails until it is declared |
| A producer claiming a cadence | Free text nobody checked | Must name a task really present in `celery_app.conf.beat_schedule` |
| Feature-flag state on the page | Only the two CS toggles, no context | Every gating flag per producer, with `persisted` distinguishing "off" from "default on" |
| Inventory read side effects | N/A | Asserted to seed no `feature_flags` rows, unlike `GET /feature-flags/{key}` |
| Endpoint authorisation | N/A | `admin:manage`, an existing token; census posture `PERMISSION`, no new debt |
| VAPID public key | Served by the subscribe flow | Dropped from this payload; whole body grepped for sentinels |
| Alembic heads | 1 | 1 — no revision added |
| i18n parity for new strings | N/A | 17 keys added to both `en` and `cy` |

## 4) Acceptance Criteria (AC)

- [x] AC-01: `GET /api/v1/notifications/inventory` returns every real channel with
  a readiness in the declared vocabulary, and `can_send` never contradicts it.
- [x] AC-02: A channel this product does not have is reported as
  `not_implemented` with a reason, rather than omitted.
- [x] AC-03: The four producers with no production caller are reported as
  `no_production_caller`, and the page says "Notifies nobody".
- [x] AC-04: An unauthenticated caller is refused, and an authenticated
  administrator **without** `admin:manage` is refused with 403.
- [x] AC-05: The census reports this endpoint's posture as `PERMISSION` with
  `admin:manage`, so `route_declarations.py` records no new authorisation debt.
- [x] AC-06: Reading the inventory creates no `feature_flags` row — count *and*
  key set identical before and after.
- [x] AC-07: No VAPID key material appears anywhere in the response body.
- [x] AC-08: The inventory router declares no method outside `{GET, HEAD}`, and
  no write is mounted at the inventory path by any router.
- [x] AC-09: A producer declaration whose module or symbol does not resolve fails
  the suite; a producer module present in the source and absent from the registry
  fails the suite; a cadence naming no real beat entry fails the suite.
- [x] AC-10: The admin panel adds no control — no switch, no checkbox, and no
  button beyond the pre-existing Compliance Schedule flag rows.
- [x] AC-11: The inventory is fetched exactly once per mount (no fetch loop).
- [x] AC-12: A 403 says the permission is missing rather than rendering an empty
  inventory; a 500 costs the inventory but not the feature-flag panel.
- [x] AC-13: No alembic revision, no column, no table; `git diff` under
  `alembic/` is empty.
- [x] AC-14: No dispatcher file edited — no `notification_service.py`, no
  `routes/notifications.py`, no `routes/push_notifications.py` — so no conflict
  with open PR #1710.
- [x] AC-15: No existing test was skipped, loosened, renamed or deleted.
- [x] AC-16: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

Run locally in `.worktrees/notif-admin-01-inventory` on `80d88bcc5` with
`/Users/davidharris/quality-governance-platform/.venv/bin/python` (3.11.15).

- [x] **Full backend unit suite** `pytest tests/unit -q` → **6,565 passed, 0
  failed, 11 skipped** in 142s. The 11 skips are pre-existing and unrelated; they
  skip identically on `origin/main`.
- [x] `pytest tests/unit/test_notification_inventory.py
  tests/unit/test_notification_inventory_route.py
  tests/unit/test_route_census_classification.py -q` → **78 passed, none
  skipped**.
- [x] **New backend tests:** 49 registry + 12 route + 13 integration = **74**.
- [x] **Frontend** `vitest run NotificationSettings.test.tsx` → **12 passed**
  (3 before this PR, +9 here). `tsc --noEmit` clean; `eslint` on both touched
  files clean.
- [x] `mypy src/ --config-file pyproject.toml` → **Success: no issues found in
  605 source files**.
- [x] `black --check src/ tests/` → 1,415 files unchanged; `isort --check-only` →
  clean; `flake8 src/ tests/` → clean.
- [x] `scripts/check_import_boundaries.py` → **OK: All import boundaries
  respected** (this is why readiness interpretation is pure and the
  `src.infrastructure` helpers are consulted by the route, not the domain module).
- [x] `scripts/check_mock_data.py --repo-root .` → `[PASS] No mock data patterns
  detected`.
- [x] `scripts/check_openapi_compatibility.py` → **Contract check PASSED**,
  additive only. The one path this PR adds is
  `/api/v1/notifications/inventory`; zero paths removed.
- [x] i18n parity for the added keys: 17 `admin.notifications.inventory.*` keys in
  `en.json` and 17 in `cy.json`. (The repository has a **pre-existing** 351-key
  `en`→`cy` gap unrelated to this PR; this change does not widen it.)
- [x] **New tests proven to bite** (each mutation reverted immediately after;
  working tree confirmed clean):
  - `sos_alert` flipped to `referenced=True` → exactly
    `test_producers_declared_active_are_reachable` and
    `test_the_known_dead_producers_are_still_recorded` fail (**2 failed, 47
    passed**).
  - `standards_assessment_links` declaration deleted → exactly
    `test_every_producer_module_in_the_source_is_declared` fails (**1 failed, 48
    passed**).
  - `safety_asset_expiry`'s `beat_task` pointed at a non-existent entry → exactly
    `test_scheduled_producers_name_a_real_celery_beat_entry` fails (**1 failed,
    48 passed**).

**Stated honestly — one unexplained red I could not reproduce.** The *first*
execution of `tests/integration/test_notification_inventory_api.py` in this
worktree failed 2 of 13:
`test_an_administrator_without_the_permission_is_refused` (admin without the
permission was not refused) and
`test_the_endpoint_is_authorisation_checked_by_a_named_permission` (census
reported posture `authenticated_only` with no permissions). I then ran the file
**six** more times — 13/13 green every time, over runtimes from 16s to 101s, so
timing is not the differentiator — and both tests also pass in isolation. I
inspected the mounted dependency tree directly and it is correct
(`permission_checker` carrying `__qgp_required_permission__ = "admin:manage"`
sits under the route), and `_iter_dependants` does no de-duplication that could
drop it. **I could not reproduce the failure and I cannot explain it**, so I am
not claiming this file is deterministically green, and I have not touched either
test to make the red go away. If it recurs in CI it should be treated as a real
signal about the census walker or the integration auth override, not as flake to
be retried past.

**Not verified:** no browser was driven; the frontend evidence is jsdom only. No
staging or production run. The integration tests use the suite's DB-free
`get_current_user` override, so **no evidence here comes from a real tenant, a
real Celery worker or a real SMTP/Twilio/VAPID configuration** — channel
readiness was exercised through the status helpers' payloads, not by sending
anything. Nothing in this PR sends a notification, so nothing about delivery is
claimed.

- [ ] Full CI — on PR.
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge).

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: An administrator opens `/admin/notifications` and reads which
  channels can send, with the server's own reason for each that cannot.
  (jsdom, stubbed fetch.)
- [x] CUJ-02: The same administrator sees that raising an SOS notifies nobody,
  named as such rather than absent from the list.
- [x] CUJ-03: A user who is authenticated but lacks `admin:manage` is refused,
  and the page tells them the permission is missing instead of showing an empty
  inventory.
- [x] CUJ-04: The inventory read fails with a 500; the page reports the failure,
  claims no readiness at all, and the Compliance Schedule flag panel still loads.
- [x] CUJ-05: Reading the inventory twice leaves `feature_flags` untouched.
- [ ] CUJ-06: The same journeys against a real tenant on a deployed environment,
  with real SMTP/VAPID/Twilio configuration — to verify on tip after deploy.

## 7) Observability & Ops

- **New signal:** none emitted. This endpoint *is* the observability — it turns
  "which channels are configured and what actually notifies anyone" from a
  grep into a request. `generated_at` stamps each snapshot.
- **No secret and no message content is logged or returned.** Only presence
  booleans and the status helpers' own notes.
- **Logging:** the route adds no log line of its own beyond the standard request
  log. A status helper that raises is swallowed deliberately and reported as "not
  configured" rather than failing the request.
- **Metrics / alerts:** none added. `summary.channels_can_send` and
  `summary.producers_without_caller` are the two numbers worth watching if anyone
  later wants a gauge; no dashboard is claimed here.
- **Runbook:** support answering "why did nobody get told?" can now check this
  panel first — a producer showing "Notifies nobody", or a channel showing "Not
  configured", is the answer rather than the start of an investigation.

## 8) Release Plan

1. Open PR on tip `80d88bcc5`. **Do not merge** — raised for review only, per the
   request.
2. Merge only after the ledger / compliance gates and `CI - Default` are green,
   and after #1710 ADMIN-03 has landed or been rebased — the two touch disjoint
   files, but both add keys to `en.json` / `cy.json` and the second to merge may
   need a trivial locale rebase.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark FR-NOTIF-ADMIN-01 conveyor **PROD → DONE**. Merge alone is not
   done.

## 9) Rollback Plan

- **Trigger:** the panel reports something an operator can show to be untrue, or
  the endpoint proves expensive or noisy under real load.
- **Rollback steps:** revert the merge commit and let the pipeline deploy the
  reverted tip. There is no schema change, no data migration, no flag to flip and
  nothing persisted, so the revert is complete on its own — the endpoint and the
  panel simply cease to exist.
- **Partial mitigation without a revert:** the panel is a single card and the
  endpoint a single `GET`; revoking `admin:manage` from a role removes access
  without a deploy.
- **Owner:** Platform Engineering (Governance UX lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/notif-admin-01-inventory`
- Base: `80d88bcc5` (#1709), rebased onto latest `origin/main`
- Files: 12 changed, +2,598 / −20 — 1 new domain registry, 1 new route, 1 new
  schema, 1 router mount, 1 frontend panel, 2 locale files, 3 new test files,
  1 extended frontend test file, plus this ledger
- Registry contents: 4 real channels, 2 declared-absent channels, 22 producers
  (18 active, 4 with no production caller, 5 schedule-driven)
- Alembic revisions added: **0**; `git diff origin/main...HEAD -- alembic/` empty
- Local evidence: 6,565 backend unit tests green; 74 new backend/integration
  tests; 12 frontend tests; mypy clean over 605 files; black / isort / flake8
  clean; import boundaries OK; OpenAPI contract check passed; 3 registry tests
  proven to fail under mutation (§5)
- Known unreproduced red on first integration run, recorded in §5 rather than
  retried away
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — one additive path, no path changed or removed;
  OpenAPI compatibility check passes; no alembic revision, no column change, no
  new table; `admin:manage` is an existing catalogue token so the permission
  vocabulary is unchanged
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A. A read behind an existing permission; there is no
  behaviour to stage and no delivery path touched
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] **No dispatcher edit.** `notification_service.py`, `routes/notifications.py`
  and `routes/push_notifications.py` are untouched — the three files open PR
  #1710 (ADMIN-03) changes. The two branches share **zero** source files; the
  only common files are `en.json` / `cy.json`, where each adds its own keys
- [x] New endpoint mounted from its own router, so `routes/notifications.py` did
  not need to be opened at all
- [x] No `Layout.tsx` and no nav edit of any kind
- [x] No Audit Builder / dashboard / `RecentCasesPanel` edits
- [x] No alembic revision; no second head
- [x] No new permission token — `admin:manage` already exists and is already
  enforced elsewhere
- [x] No test skipped, loosened, renamed or deleted to go green
- [x] The admin panel adds no control, so nothing on it can become a setting that
  fails to persist — the exact defect #1707 deleted
