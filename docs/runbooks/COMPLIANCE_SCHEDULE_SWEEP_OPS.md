# Compliance Schedule sweep operations

Running, reading, and stopping the daily sweep that notifies owners and admins about
compliance obligations coming due. Read the dry-run section before you trigger anything
in an environment that has never run it.

| Fact | Value |
|---|---|
| Task name | `src.infrastructure.tasks.compliance_schedule_notification_tasks.sweep_compliance_schedule_due` |
| Module | `src/infrastructure/tasks/compliance_schedule_notification_tasks.py` |
| Queue | `notifications` |
| Scheduled | **No.** Registered in `CELERY_TASK_MODULES`, deliberately absent from `beat_schedule` |
| Writes | `notifications` rows with `entity_type = 'compliance_requirement'` |
| Gates | `COMPLIANCE_SCHEDULE_ENABLED` (opener) and the `compliance_schedule_kill_switch` feature flag |

Scheduling it is a separate change from registering it, so that switching the sweep off
is a one-line revert rather than a code edit under pressure. Until that change lands the
sweep runs only when someone triggers it by hand, which is also how the first run in any
environment should happen.

---

## 1. Dry run first. Always, on a new environment

The register holds *historical* due dates. A tenant that imported five years of fire
risk assessments and PAT tests has a backlog of obligations that are already overdue or
already inside a reminder band, and none of them have been notified yet. The first real
run does not deliver a trickle — it delivers the whole backlog at once, in one batch, to
the owners and admins of every tenant.

`dry_run=True` computes the entire run and writes nothing: each tenant's transaction is
rolled back instead of committed. The `notifications_created` counter it reports is the
number of notifications a real run would deliver against the register as it stands right
now. Read that number, decide whether it is a number you are willing to put in people's
inboxes today, and only then run for real.

Two things to know about a dry run:

- It still takes the per-tenant advisory lock. A dry run started while a real run is in
  flight reports those tenants under `tenants_skipped_locked` and its totals are
  therefore incomplete, not zero-because-nothing-is-due.
- It is honest about the opener and the kill switch. A dry run against a closed module
  reports all-zero counters, which is not the same as "nothing to send" (section 5).

---

## 2. Triggering it

### Option A — from the worker container (preferred)

The worker container already has the application, its configuration, and broker
credentials, and this is where [`IMPORT_CELERY_DLQ_OPS.md`](./IMPORT_CELERY_DLQ_OPS.md)
runs its `celery inspect` commands. Worker sites are named `${API_WEBAPP}-worker` — see
[`CELERY_WORKER_BEAT_DEPLOY.md`](./CELERY_WORKER_BEAT_DEPLOY.md).

```bash
APP=src.infrastructure.tasks.celery_app.celery_app
TASK=src.infrastructure.tasks.compliance_schedule_notification_tasks.sweep_compliance_schedule_due

# Confirm a worker is alive and has the task in its registry.
celery -A "$APP" inspect ping
celery -A "$APP" inspect registered | grep sweep_compliance_schedule_due

# Dry run.
celery -A "$APP" call "$TASK" -k '{"dry_run": true}' --queue notifications

# Real run, once you have read the dry-run counters.
celery -A "$APP" call "$TASK" --queue notifications

# Replay a specific reference date (see the warning in section 4).
celery -A "$APP" call "$TASK" -k '{"dry_run": true, "today": "2026-08-03"}' --queue notifications
```

`celery call` prints a task id and nothing else. Fetch the counters from the result
backend:

```bash
celery -A "$APP" result <task-id>
```

**Pass `--queue notifications` explicitly.** `celery call` dispatches through
`app.send_task`, and the queue declared on the `@celery_app.task` decorator is applied by
`apply_async`, not by `send_task` — verified against Celery 5.6.2, the pinned version. A
call without `--queue` is routed to `task_default_queue`, which is `default`. The worker
consumes `default` as well under the entrypoint's own defaults, so it would still run
today; it would strand silently in a broker queue nobody reads if `CELERY_QUEUES` is ever
narrowed. Naming the queue costs nothing and removes the failure mode.

**Shell access to the worker site is not something this repository documents.**
`az webapp ssh --name <site> --resource-group <rg>` is the pattern used elsewhere for the
API site, but whether SSH is enabled on the `-worker` sites has not been confirmed. If it
is not, use Option B.

### Option B — broker-only client

Dispatching a task by name needs the broker, not the application. Build a lightweight
Celery client the way `scripts/celery/smoke_inspect_ping.py` does — it exists precisely
so a host without the full dependency tree can talk to the broker, and it carries the
`rediss://` SSL normalisation that Azure Redis requires — and call `send_task` with the
queue named explicitly:

```python
app.send_task(
    "src.infrastructure.tasks.compliance_schedule_notification_tasks.sweep_compliance_schedule_due",
    kwargs={"dry_run": True},
    queue="notifications",
)
```

There is **no HTTP endpoint that triggers this sweep.** Do not go looking for one.

---

## 3. Reading the result

The task returns a `ComplianceSweepResults` dict. It is also written to the worker log at
the end of every run as `Compliance schedule sweep completed: {...}`, which is how to
recover the numbers when the result has expired from the backend — query Log Analytics,
not `az webapp log download`, for the reasons in
[`CELERY_WORKER_BEAT_DEPLOY.md`](./CELERY_WORKER_BEAT_DEPLOY.md).

| Field | Meaning | Reading it |
|---|---|---|
| `tenants_considered` | Active tenants found at the start of the run | `0` means the module is closed **or** there are no active tenants — section 5 |
| `tenants_swept` | Tenants scanned and committed (or rolled back, on a dry run) | Should equal `tenants_considered` on a clean run |
| `tenants_skipped_locked` | Tenants another sweep already held the advisory lock on | Above zero means two runs overlapped. Harmless; the other run did the work |
| `tenants_skipped_closed` | Tenants left unswept because the kill switch was engaged mid-run | Above zero is an operator action, expected only if someone engaged the switch |
| `requirements_scanned` | Active, non-deleted requirements read across all swept tenants | `0` everywhere is suspicious — section 5 |
| `in_band` | Requirements inside a reminder band (`overdue`, `due_7`, `due_30`, `due_60`) | A small fraction of `requirements_scanned` in steady state |
| `notifications_created` | Rows written. **On a dry run, rows that *would* be written** | The number that matters. Large on a first run, near zero afterwards |
| `notifications_skipped_existing` | This exact reminder already existed | **High is healthy.** See below |
| `notifications_skipped_conflict` | The database refused a duplicate write | Above zero means two workers overlapped mid-insert. Investigate, do not ignore |
| `recipients_unresolved` | In-band requirements with nobody to notify | Above zero is a configuration fault someone must fix. See below |
| `dry_run` | Whether this run wrote anything | Check it. A dry run's `notifications_created` is a forecast, not a delivery |
| `evaluated_at` | UTC ISO timestamp taken at the start of the run | Also stamped into every row's `extra_data.evaluated_at`; use it to scope a cleanup |
| `admin_role` | Role name used to resolve admin recipients | Should be the real admin role name for these tenants. Section 5 |

### A healthy steady-state run

`tenants_swept == tenants_considered`, both skip-tenant counters `0`, `in_band` a modest
number, `notifications_created` at or near `0`, `notifications_skipped_existing`
comfortably larger than `notifications_created`, and `recipients_unresolved` at `0`.

`notifications_skipped_existing` being high is the *design working*. A requirement stays
inside a band for days: something 40 days out is in `due_60` today and still in `due_60`
tomorrow. The reminder is keyed on requirement, occurrence date and band, so the second
day's sweep finds the row it wrote yesterday and skips it. A day with a large
`skipped_existing` and a small `created` is a quiet day, not a broken one.

`notifications_skipped_conflict` above zero means the fast-path check and the insert were
separated by another worker doing the same thing: two sweeps raced inside one tenant, and
the partial unique index `uq_notifications_compliance_dedupe` refused the second write.
No duplicate reached a user — that is what the index is for — but on PostgreSQL, with the
per-tenant advisory lock working, this should be `0`. A non-zero count means either the
lock did not apply (it is a no-op on non-PostgreSQL databases) or something other than
this sweep wrote the same key. Check for a redelivered task — `task_acks_late` is on, so a
worker lost mid-run has its task redelivered — and check whether more than one sweep was
triggered.

`recipients_unresolved` above zero means a requirement is inside a reminder band and
there is no one to tell: it has no owner, *and* the tenant has no active admin under the
role named in `admin_role`. That is a statutory obligation nobody is being chased about.
It is counted rather than skipped silently for that reason. Fix it by assigning an owner
to the requirement, or by ensuring the tenant has an active user holding the admin role.

### Detecting a tenant that failed

There is **no counter for a tenant that raised an exception.** A tenant that fails is
logged and the sweep continues with the rest, which is the right behaviour, but it leaves
no field in the result dict. Detect it by arithmetic:

```text
tenants_considered - tenants_swept - tenants_skipped_locked - tenants_skipped_closed
```

Anything above zero is that many tenants that failed. Find them in the worker log under
`Compliance schedule sweep failed for tenant <id>; continuing with the rest`, which
carries the traceback.

### When a run is retried

The task's soft time limit is 300 seconds and its hard limit is 600. A first run against
a large backlog across many tenants can exceed the soft limit; the task catches that,
logs `Compliance schedule sweep failed`, and retries after 300 seconds, up to three
times, before the failure lands in the DLQ ([`IMPORT_CELERY_DLQ_OPS.md`](./IMPORT_CELERY_DLQ_OPS.md)).

A retry is safe: each tenant commits its own transaction, so work already done stays
done, and the retried run reports it as `notifications_skipped_existing` rather than
sending anything twice. But **only the final attempt's counters are returned.** The
numbers from the attempts that timed out exist only in the log. If the totals look too
small for a first run, check the log for earlier attempts before concluding the backlog
was smaller than the dry run said.

---

## 4. The `today` override

`today` is an ISO date that replaces the reference point used to classify bands. It does
not change what is due; it changes which band a requirement falls into.

Use it to replay a day the sweep was not run. Be aware that the reminder key includes the
band, so replaying with an earlier date can classify an occurrence into a *different*
band than today's run would — and a different band is a different key, which is a second
notification for the same occurrence to the same person. Dry-run any `today` override
first and compare `notifications_created` against your expectation.

---

## 5. Troubleshooting

### `tenants_considered: 0`

The module is closed, or there genuinely are no active tenants. The sweep asks whether
Compliance Schedule is open before it opens a session at all, and returns all-zero
counters when the answer is no. Distinguish the two by the log line: a closed module logs
`Compliance schedule sweep: module closed, nothing swept`.

Both gates must be satisfied. Check them in this order:

1. **The opener.** `COMPLIANCE_SCHEDULE_ENABLED` must be true in the environment. It is
   checked first and short-circuits, and it is `false` by default everywhere. Changing it
   requires a restart or redeploy of the worker — it is configuration, not a flag.
2. **The kill switch.** No `feature_flags` row with `key = 'compliance_schedule_kill_switch'`
   and `enabled = true`.

```sql
SELECT key, enabled, updated_at FROM feature_flags
WHERE key = 'compliance_schedule_kill_switch';

SELECT count(*) FROM tenants WHERE is_active = true;
```

If neither explains it, look for the warning
`Compliance Schedule kill switch could not be read` from
`src.domain.services.compliance_schedule_kill_switch`. A switch that was already observed
engaged stays engaged when the database read fails; only a successful read saying
`enabled = false` clears it.

### `requirements_scanned: 0` across every tenant

Either there are genuinely no active requirements, or the tenant GUC is not doing what
the query needs it to. The sweep binds `app.current_tenant_id` per tenant, transaction-
locally. Today the worker connects as a role with `BYPASSRLS`, so an unbound GUC would
still see rows; after the row-level-security cutover an unbound or wrongly bound GUC
returns *zero* rows and the sweep reports success having notified nobody. That is the
failure mode this counter is for.

Confirm which it is directly against the database:

```sql
SELECT tenant_id, count(*)
FROM compliance_requirements
WHERE is_active = true AND deleted_at IS NULL
GROUP BY tenant_id
ORDER BY tenant_id;
```

Rows here with `requirements_scanned: 0` in the result means the GUC path is broken, not
the register. Rows absent here means the register is empty and the sweep is correct.

### `requirements_scanned` is healthy but `notifications_created` is `0` and `recipients_unresolved` is high

Check `admin_role` in the result against the actual admin role name for those tenants.
It comes from `COMPLIANCE_SCHEDULE_ADMIN_ROLE` and defaults to `admin`; a value that
matches no role resolves to no admins at all, which leaves owners as the only recipients
and every unowned requirement unresolved.

### `NotRegistered`

The worker did not import the module. `celery inspect ping` still answers, because a
worker with an empty registry is a healthy process — it only fails when something is sent
to it.

1. `celery -A "$APP" inspect registered | grep sweep_compliance_schedule_due`
2. Confirm the deployed worker image is built from a commit where
   `src.infrastructure.tasks.compliance_schedule_notification_tasks` is in
   `CELERY_TASK_MODULES` in `src/infrastructure/tasks/celery_app.py`. Compare
   `GET /api/v1/meta/version` `build_sha` against the intended tip.
3. Redeploy the worker. A worker running an older image than the API is the usual cause.

### Nothing happens at all — no result, no log line

The message never reached a worker. Check `celery -A "$APP" inspect ping` for a pong,
check `CELERY_QUEUES` on the worker includes `notifications`, and check `/readyz` reports
`redis=connected`.

---

## 6. The kill switch, and what it cannot do

The switch is the `compliance_schedule_kill_switch` row in `feature_flags`, following the
same pattern as [`AI_COPILOT_KILL_SWITCH.md`](./AI_COPILOT_KILL_SWITCH.md). `enabled = true`
means *the kill is engaged*; no row and `enabled = false` both leave the opener in charge.
Only the `enabled` column is read — `rollout_percentage` and `tenant_overrides` are
ignored, because a partially applied kill is not a useful state.

### Engaging it

Option A, the API (preferred — leaves a `feature_flag_toggle` audit entry, superuser JWT
required):

```bash
# First time only: create the row.
curl -sS -X POST "$BASE/api/v1/feature-flags/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"key": "compliance_schedule_kill_switch", "name": "Compliance Schedule kill switch", "enabled": true}'

# Thereafter: engage or release.
curl -sS -X PATCH "$BASE/api/v1/feature-flags/compliance_schedule_kill_switch" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

Option B, SQL, when the API is not usable:

```sql
INSERT INTO feature_flags (id, key, name, enabled)
VALUES (gen_random_uuid(), 'compliance_schedule_kill_switch', 'Compliance Schedule kill switch', true)
ON CONFLICT (key) DO UPDATE SET enabled = true, updated_at = now();
```

Either route applies on the same schedule: the sweep reads this row itself rather than
going through `FeatureFlagService`'s untimed process cache.

### What it does, exactly

- **It prevents future runs.** A sweep triggered after the switch takes effect asks
  before opening a session, logs `module closed, nothing swept`, and returns zeros.
- **It stops an in-flight run at the next tenant boundary.** The sweep re-asks the switch
  before each tenant. The remaining tenants are counted in `tenants_skipped_closed` and
  the run logs `kill switch engaged mid-run, stopping with N tenant(s) unswept`.

### What it cannot do

- **It does not retract notifications already sent.** Rows already committed stay in
  their recipients' inboxes. Deleting them is a separate, deliberate act — section 7.
- **It does not interrupt the tenant currently being swept.** That tenant finishes and
  commits its notifications. The switch stops the *next* one.
- **It is not instant.** Each process caches the verdict for **30 seconds** (5 seconds
  after a failed read). Engage it, wait 30 seconds, then verify. There is nothing to
  restart.
- **It cannot open the module.** The opener is checked first and short-circuits. Turning
  the sweep on still needs `COMPLIANCE_SCHEDULE_ENABLED` and a redeploy.

### Releasing it

Set `enabled = false`, or delete the row. The sweep is runnable again within the same 30
seconds, provided `COMPLIANCE_SCHEDULE_ENABLED` is still true for that environment.

---

## 7. Rollback levers, least severe first

### 1. Engage the kill switch — seconds, no deploy

Section 6. This is the first lever in almost every situation: it is reversible, leaves an
audit trail, and needs no release.

### 2. Remove the module from `CELERY_TASK_MODULES` and deploy

Delete `"src.infrastructure.tasks.compliance_schedule_notification_tasks"` from
`CELERY_TASK_MODULES` in `src/infrastructure/tasks/celery_app.py` and redeploy the
worker. The task becomes unrunnable rather than merely closed: any attempt raises
`NotRegistered` and lands in the DLQ. Note that
`tests/unit/test_compliance_schedule_sweep_registration.py` asserts the module *is* in
that tuple, so this is a deliberate change with a test to update, not a hotfix. Reach for
it when the kill switch is not enough — for example if the sweep is failing before it
reaches the switch.

### 3. Revert the PR

The full revert. The sweep, its builders, and the dedupe index are separate changes;
reverting the sweep alone leaves the index and the builders in place, which is harmless.

### 4. Delete notifications already written

Independent of all of the above, and the only way to undo delivery. `notifications` has
no soft delete, so this is a hard `DELETE`. Count before you delete, and scope it.

```sql
-- What is in scope. Every row this sweep has ever written, and nothing else:
-- the sweep is the only writer of this entity_type.
SELECT count(*) FROM notifications
WHERE entity_type = 'compliance_requirement';

-- Narrow to one run using the timestamp the sweep stamps on every row.
SELECT count(*) FROM notifications
WHERE entity_type = 'compliance_requirement'
  AND extra_data ->> 'evaluated_at' = '<evaluated_at from the result dict>';

-- Then delete the same set. Run inside a transaction and check the row count
-- before committing.
BEGIN;
DELETE FROM notifications
WHERE entity_type = 'compliance_requirement'
  AND extra_data ->> 'evaluated_at' = '<evaluated_at from the result dict>';
-- COMMIT;  -- or ROLLBACK if the count is not what you expected
```

Deleting rows makes them eligible to be created again: the sweep's de-duplication is a
lookup against existing rows plus a unique index, both of which stop applying once the
row is gone. Engage the kill switch **before** deleting, or the next run will re-send
what you just removed.

---

## 8. Tenant isolation

Worth stating because the closest precedent in this repository gets it wrong.

- **Admin recipients are scoped strictly to the tenant.** Admins are selected with
  `User.tenant_id == tenant_id` and nothing else. There is no NULL-tenant fallback, so no
  user can receive a notification naming another customer's obligation. If you see one,
  that is a serious defect, not a configuration choice.
- **The GUC is bound per tenant.** `app.current_tenant_id` is set transaction-locally for
  each tenant's session, so the queries are correct both today, where the worker role has
  `BYPASSRLS`, and after the row-level-security cutover. This is also why the sweep is a
  loop over tenants rather than one query across all of them.
- **A per-tenant PostgreSQL advisory lock stops two runs duplicating work.**
  `pg_try_advisory_xact_lock` is taken per tenant; a second sweep that cannot take it
  skips that tenant and counts it in `tenants_skipped_locked`. The lock is not what makes
  duplicates impossible — the partial unique index is — but it stops two workers doing
  the same work and reporting it twice. The lock is a no-op on non-PostgreSQL databases.

---

## Related

- [`COMPLIANCE_SCHEDULE_ROLLOUT.md`](./COMPLIANCE_SCHEDULE_ROLLOUT.md) — module gates, wave plan, enabling the surface
- [`AI_COPILOT_KILL_SWITCH.md`](./AI_COPILOT_KILL_SWITCH.md) — the kill switch pattern this one copies
- [`IMPORT_CELERY_DLQ_OPS.md`](./IMPORT_CELERY_DLQ_OPS.md) — worker health, DLQ inspection and retry
- [`CELERY_WORKER_BEAT_DEPLOY.md`](./CELERY_WORKER_BEAT_DEPLOY.md) — worker/beat sites, and how to read their logs
- `src/infrastructure/tasks/compliance_schedule_notification_tasks.py` — the sweep, and why it is built this way
- `src/domain/services/compliance_schedule_kill_switch.py` — the switch and its cache
- `src/domain/services/compliance_schedule_notifications.py` — bands, recipients, and the reminder key
