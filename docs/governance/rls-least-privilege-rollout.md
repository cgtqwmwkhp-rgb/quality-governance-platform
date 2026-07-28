# C-27: switching the application off `rolbypassrls`

Status: **CUT-0 and CUT-1 delivered. The cutover is blocked at CUT-2 and must not be
attempted.**

The `CUT-n` steps below are the cutover sequence for this change only. They are not
the repository's release Gate 0–5 in `.github/PULL_REQUEST_TEMPLATE.md`, which are a
separate and unrelated checklist.

## The finding

The application connects to PostgreSQL as the Azure administrator login
(`qgpadmin`), which holds `rolbypassrls`. PostgreSQL skips row-level security
entirely for such a role. Every `tenant_isolation` policy on the estate therefore
enforces nothing for the application. The policies are correct and completely
inert.

This is not a policy defect. It is a connection-identity defect, and the fix is a
different role — but the role change is the *last* step, not the first.

## What was verified, and what was not

Direct production database access is firewalled, so nothing below was measured
against production.

**Verified** by building a database with the full 215-migration alembic chain on
PostgreSQL 14 and interrogating `pg_policy`, `pg_class` and
`information_schema`:

- 21 tables carried a `tenant_isolation` policy before this work. All 21 had both
  `relrowsecurity` and `relforcerowsecurity` set, and a `USING` and `WITH CHECK`
  clause of `tenant_id = current_setting('app.current_tenant_id', true)::int`.
- The GUC is `app.current_tenant_id`. There is no `app.tenant_id` anywhere in the
  codebase.
- `set_config(name, value, true)` reverts to the **empty string**, not to unset,
  on COMMIT, on ROLLBACK and on `DISCARD ALL`. `''::int` raises
  SQLSTATE 22P02. Reproduced through the application's own
  `create_async_engine` + `AsyncAdaptedQueuePool`.
- `controlled_documents` and `controlled_document_versions` had no RLS at all,
  despite `RLS_TABLES` listing them.
- Of the 21 policy tables, only `users` and `workflow_rules` have a nullable
  `tenant_id` on a freshly migrated schema. The other 19 are `NOT NULL`.
- `init_db()` (the only runtime DDL) runs only when `settings.is_development`, so
  the production application needs no `CREATE` privilege.
- `session_replication_role = replica` does **not** relax row-level security.

**Inferred, and requiring confirmation against production before the cutover:**

- That the production application role is in fact `qgpadmin`. The runtime DSN comes
  from Key Vault and is not in the repository; `qgpadmin` appears in
  `infra/main.bicep` and the setup scripts as the *administrator login*.
- Which of the 21 policy tables hold rows with a NULL `tenant_id` in production.
  The `NOT NULL` constraints above were applied by *data-conditional* migrations
  that skip when rows are non-conforming, so production may still permit NULL where
  a fresh database does not.
- The production count of NULL-tenant rows in policy tables. Run
  `scripts/ops/run026/rls_role_readiness.py` against production to obtain it.

## Correction to the original framing

The brief was that ~1,696 tenant-less rows across 23 tables would vanish the moment
the role changed, led by `vehicle_defects` (623), `vehicle_registry` (362),
`audit_responses` (313) and `audit_questions` (118).

**None of those tables has a row-level security policy.** RLS applies only to tables
where it is enabled, so a tenant-less row in a table with no policy is entirely
unaffected by the role change. The blast radius is the *intersection* of "has a
policy" and "holds NULL `tenant_id`", and on a fresh schema that intersection is
just `users` and `workflow_rules`.

Those rows still need attributing — they are invisible to their rightful owner in
any tenant-filtered query today, which is the C-01/TEN2 work — but they are not what
gates this change. Two much larger problems are, and neither is about data at all.

## The two real blockers

### CUT-1 — the predicate failed loud, not closed (fixed in this change)

`apply_tenant_guc` binds the tenant with `set_config(..., true)`, which is
transaction-local. When the transaction ends, PostgreSQL restores the session value
of the GUC, and for a custom GUC only ever set transaction-locally that value is the
empty string. `''::int` raises 22P02 and aborts the transaction, so every subsequent
statement on that connection fails too.

So on a **pooled** connection that had already served one tenant-scoped request, a
later request with no tenant would not have returned an empty list — it would have
returned HTTP 500, and taken the rest of the session with it. Only the first
transaction on a brand-new connection behaved as the docstrings claim.

Fixed by `20260902_rls_guc_guard`, which rewrites all 21 predicates as
`tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int` and
adopts the two missing tables. Inert while the app still bypasses RLS.

### CUT-2 — authentication cannot resolve a tenant (NOT fixed; this is the blocker)

`users` is under FORCE RLS. Authentication reads it *before* it knows the tenant,
because the tenant is a column on the row being fetched:

- `src/domain/services/auth_service.py:72` — login, by email.
- `src/api/dependencies/__init__.py:92` — `get_current_user`, by id.

With no tenant bound there is nothing to bind, so under a non-bypass role both
lookups match zero rows. Login fails for every user and every existing token 401s.
Measured: `qgp_app` sees 0 of 2 users with no GUC set. The JWT carries no tenant
claim (`src/core/security.py:72`), so the GUC cannot be bound before the read
either.

No backfill fixes this. It is the shape of the code. It must be fixed before the
role changes, and it is deliberately **not** fixed here — it is a change to the
authentication path, and mixing that into an infrastructure PR is how a
security-sensitive regression gets waved through.

Three viable approaches, in the order I would try them:

1. **A `SECURITY DEFINER` lookup function** owned by a bypass role, returning only
   the columns auth needs, with `EXECUTE` granted to `qgp_app`. The single
   cross-tenant read in the system becomes one auditable function with a fixed
   shape. Most work, best result.
2. **A tenant claim in the access token**, so `get_current_user` can bind the GUC
   before reading `users`. Fixes token validation but not login-by-email, and
   invalidates every issued token unless a migration period is honoured.
3. **Exempt `users` from FORCE RLS** and rely on application-level filtering for it.
   Least work, weakest guarantee, and `users` is the table most worth protecting.

## The ordering requirement

Each step must be complete and verified before the next begins.

| Step | What | Status |
|---|---|---|
| CUT-0 | Least-privilege role `qgp_app` created with grants, no credential | **done** (`20260903_app_lp_role`) |
| CUT-1 | All policy predicates survive an empty GUC; the two unprotected tables adopted | **done** (`20260902_rls_guc_guard`) |
| CUT-2 | Authentication can resolve a tenant without already having one | **blocked — not started** |
| CUT-3 | Every background / cross-tenant code path audited for an unbound GUC | not started |
| CUT-4 | NULL `tenant_id` remediated or explicitly excepted, in policy tables only | not started |
| CUT-5 | Staging cutover; readiness script clean; soak | not started |
| CUT-6 | Production cutover, human-authorised | not started |

CUT-0 and CUT-1 are safe to deploy at any time and change nothing observable, because
a `rolbypassrls` role never evaluates a policy. That is the point of doing them
first.

### What breaks if the sequence is not followed

- **Skipping CUT-2**: total authentication outage. Nobody can log in; every request
  with an existing token returns 401. Recovery is reverting the connection string.
- **Skipping CUT-1**: intermittent HTTP 500s (`invalid input syntax for type
  integer: ""`) on whichever requests happen to land on a recycled connection,
  rather than a clean empty result. Load-dependent, so it may look fine in a smoke
  test and fail under traffic.
- **Skipping CUT-3**: Celery tasks and cross-tenant sweeps silently process zero
  rows. No error, no alert. `training_matrix_upload_reminder_tasks.py:153`,
  `regulatory_watch_actions.py:108` and `action_service.py:254` all query `users`
  with no tenant filter and would need the GUC bound per tenant.
- **Skipping CUT-4**: rows with a NULL `tenant_id` in a policy table disappear from
  the application. On a fresh schema that is `users` and `workflow_rules` only; a
  tenant-less `users` row means that account is permanently locked out, and a
  tenant-less `workflow_rules` row means that automation silently stops firing.
- **Missing a grant**: `permission denied for table X` on first access. The readiness
  script checks every table and every sequence for this, because
  `ALTER DEFAULT PRIVILEGES` only covers objects created by the role that set it —
  if the migration identity ever changes, new tables arrive ungranted.

## Role design

Two roles. Only the application's identity changes.

**`qgp_app`** — the application runtime identity. `NOLOGIN`, no password,
`NOBYPASSRLS`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`. Granted
`CONNECT` on the database, `USAGE` on `public`,
`SELECT, INSERT, UPDATE, DELETE` on all tables, `USAGE, SELECT` on all sequences,
and the same by default on objects future migrations create.

It is deliberately **not** granted `TRUNCATE`, `REFERENCES`, `TRIGGER`, or `CREATE`
on the schema. `TRUNCATE` matters most: PostgreSQL has no per-row TRUNCATE check, so
a role holding it can empty a tenant-scoped table across every tenant regardless of
`tenant_isolation`.

It is created locked. Granting `LOGIN` and a password from Key Vault is a runbook
step, so no credential exists in version control and the role cannot be used by
accident before the cutover is authorised. The migration does grant `qgp_app` to the
migration identity, which lets the readiness check and the integration tests assume
the role via `SET ROLE` without any credential existing.

**Migrations keep the existing administrator credential, unchanged.** This is
deliberate:

- `20260901_case_tenant_nn` already *refuses to run* without
  `rolsuper`/`rolbypassrls`, because `COUNT(*) WHERE tenant_id IS NULL` returns 0
  under FORCE RLS while the `SET NOT NULL` heap scan still aborts. Data-repair
  migrations must see every row.
- The chain issues `CREATE EXTENSION` (`pg_trgm`) and `CREATE ROLE`.
- DDL against a FORCE-RLS table from a non-bypass role is its own hazard: a backfill
  inside `ALTER TABLE` sees only rows matching the current GUC.

`qgp_migrations` (`NOLOGIN BYPASSRLS`, from `20260222_add_row_level_security`) exists
for this purpose and is left alone. Giving it `LOGIN` and a password would create a
second privileged credential to rotate while the administrator credential the deploy
workflow already uses keeps working — and it would change the deployment path in the
same change as the RLS switch-on. Those should be separated.

## Before the cutover

```sh
env -u DATABASE_URL -u PRODDB -u STAGING_DB \
  DATABASE_URL='postgresql+asyncpg://<admin>@<host>/<db>' \
  python -m scripts.ops.run026.rls_role_readiness --json
```

Read-only; there is no `--apply`. Exits 0 only when every gate passes. It must be run
as an admin role: under a non-bypass role its NULL counts would be filtered to zero
by the very policies it is assessing, and it says so rather than reporting a zero it
cannot stand behind.

## What remains untested

- Anything against production or staging. Every measurement here is from a local
  PostgreSQL 14 database built by the real migration chain.
- The application running end-to-end as `qgp_app`. The policies, grants and role
  attributes are proven; a full request path under the new role is not, and cannot
  be until CUT-2 lands.
- PostgreSQL 16, which CI uses and Azure may run. The empty-string GUC revert was
  verified on 14 only. The integration test asserts the revert behaviour explicitly,
  so CI will say so if 16 differs.
- Query-plan impact of the `NULLIF` wrapper on large tables. The expression is still
  a stable, once-per-query one, so index quals on `tenant_id` should be unaffected,
  but this was not benchmarked.
