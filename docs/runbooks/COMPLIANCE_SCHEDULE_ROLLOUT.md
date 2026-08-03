# Compliance Schedule rollout

Skeleton runbook for the Compliance Schedule module. Expand with Wave 2 soak
criteria before production enablement.

## Gates (two, subtract-only on the second)

| Gate | Mechanism | Default |
|---|---|---|
| Opener | `COMPLIANCE_SCHEDULE_ENABLED` / `settings.compliance_schedule_enabled` | `false` |
| Kill | `feature_flags.key = compliance_schedule_kill_switch` (`enabled=true` means **kill**) | no row / `false` |

The kill switch follows the AI Copilot pattern
(`src/domain/services/compliance_schedule_kill_switch.py`): 30s success TTL,
5s error retry, own session factory, sticky engaged on read failure. It
**cannot** open the module when configuration is off.

Frontend nav uses `useFeatureFlag('compliance_schedule')` (default **false**).
For a staging demo, inject `window.__FEATURE_FLAGS__.compliance_schedule = true`
(or `localStorage.setItem('ff_override_compliance_schedule','true')`) in addition
to the backend opener.

See also: [`AI_COPILOT_KILL_SWITCH.md`](./AI_COPILOT_KILL_SWITCH.md).

## Wave plan

### Wave 0 — Foundations (shipped)

- Schema: templates / requirements / records + RLS + `capasource.compliance_record`
- Catalogue seed from `specs/compliance-schedule/catalogue.json`
- Policy pure functions + unit tests
- Flag + kill switch + ADR-0020 + module brief

Nothing user-visible. Flag stays off.

### Wave 1 — Vertical slice (this PR)

- API CRUD + complete-record; FE list/detail; evidence attach
- Permissions enforced on every route (`compliance_schedule:read|create|update`)
- Flag still defaults **off**

#### Staging demo — turn on (manual; not CI)

1. **Migrate** (if not already): apply Alembic head including `20260913_cs_wave0`.
2. **Opener env** on the App Service / container:
   - `COMPLIANCE_SCHEDULE_ENABLED=true`
   - Redeploy (or restart) so `settings.compliance_schedule_enabled` is true.
3. **FE flag** (nav + pages):
   - Temporary: browser console  
     `localStorage.setItem('ff_override_compliance_schedule','true')` then refresh  
   - Or inject `window.__FEATURE_FLAGS__ = { ..., compliance_schedule: true }` from the host page.
4. **Role grants** (required for non-superusers) — see below. Superusers bypass
   permission checks and can demo without grants.
5. Confirm kill switch is **not** engaged:
   - No `feature_flags` row with `key=compliance_schedule_kill_switch` and `enabled=true`.
6. Smoke: `/compliance-schedule` lists catalogue; activate a template; complete an occurrence.

#### Wave 1 grant procedure (do **not** run from CI)

`ADMIN_ROLE_PERMISSIONS` in `src/domain/authz/catalogue.py` is a **proposal only**.
Nothing applies it automatically. Before staging demo to non-superusers, grant the
three tokens to the admin role (or a dedicated compliance role) via a **reviewed**
SQL/API change.

Tokens:

- `compliance_schedule:read`
- `compliance_schedule:create`
- `compliance_schedule:update`

**Preferred (API):** Admin Console → Roles → edit the staging admin role → add the
three tokens → save. The role `permissions` field is a JSON string array.

**SQL sketch (staging only; review before execute):**

```sql
-- Inspect current admin role permissions (adjust role name/id for the tenant).
SELECT id, name, permissions FROM roles WHERE lower(name) = 'admin';

-- Merge the three tokens into the JSON array (example for a JSON-array string).
-- Replace :role_id. Validate JSON after update.
UPDATE roles
SET permissions = (
  SELECT json_group_array(value)
  FROM (
    SELECT value FROM json_each(permissions)
    UNION
    SELECT 'compliance_schedule:read'
    UNION
    SELECT 'compliance_schedule:create'
    UNION
    SELECT 'compliance_schedule:update'
  )
)
WHERE id = :role_id;
```

On PostgreSQL, prefer a reviewed script that parses `permissions::jsonb`, appends
missing tokens with `||`, and writes back — do **not** paste unreviewed JSON into
production. CI must never apply live grants.

**Verify:** sign in as a non-superuser admin; `GET /api/v1/compliance-schedule/stats`
returns 200 (with opener on). A user without the tokens receives 403.

### Wave 2 — Integrations

- CAPA writer from failed/missed records
- Calendar loader, notification sweep, library filing bridge
- Worker/beat redeploy, staging soak, then production flag on for Plantexpand

## Kill switch ladder

1. **Engage kill** (seconds): set `compliance_schedule_kill_switch.enabled = true`
   via feature-flags API or SQL. Wait ≤30s for all pods.
2. **Confirm:** module routes return 404 / FE hides nav.
3. **Release kill:** set `enabled = false` (or delete the row). Reopens only if
   `COMPLIANCE_SCHEDULE_ENABLED` is still true.
4. **Hard close:** set `COMPLIANCE_SCHEDULE_ENABLED=false` and redeploy (opener).

## Rollback sketch

- Flag off + kill engaged → no user surface.
- Schema rollback: reverse `20260913_cs_wave0` only if no tenant data must be
  retained; `capasource` ADD VALUE is irreversible (label may remain unused).

## Related

- ADR-0020 occurrence model
- `docs/product/module-briefs.md` §42 Compliance Schedule
