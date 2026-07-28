# Change Ledger (CL-RUN026-LEASTPRIV)

> **Read this first.** This PR does **not** change the connection role, and merging it
> changes nothing observable in production. It delivers the first two steps of the C-27
> cutover and *proves the cutover is not yet safe*. One test in here is designed to keep
> the cutover blocked. See `docs/governance/rls-least-privilege-rollout.md`.

## 1) Summary
- **Feature / Change name:** C-27 — groundwork for taking the application off `rolbypassrls`
- **User goal (1–2 lines):** The 21 `tenant_isolation` policies enforce nothing, because the app connects as a `rolbypassrls` role. This makes the policies *survivable* under a non-bypass role, creates the least-privilege role, and documents the ordered sequence so the role change can be made without an outage.
- **In scope:** hardening all `tenant_isolation` predicates against an empty GUC; adopting two tables that had no policy at all; creating `qgp_app` locked (`NOLOGIN`, no password); a read-only readiness script; unit + Postgres integration tests; the rollout/blast-radius document
- **Out of scope, deliberately:** the connection string; granting `qgp_app` `LOGIN`; the authentication-bootstrap fix (CUT-2); backfilling NULL `tenant_id`; anything executed against production or staging
- **Feature flag / kill switch:** none needed — `qgp_app` is created `NOLOGIN` with no credential, so it cannot be used until a human grants it one. That is the kill switch.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** none
- **Backend (handlers/services):** none. `src/infrastructure/middleware/tenant_context.py` gains two constants (`TENANT_GUC`, `TENANT_ISOLATION_PREDICATE`) and comments. No behaviour change.
- **APIs (endpoints changed/added):** none
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** none
- **Database (migrations/entities/indexes):** two migrations, **no schema change**.
  - `20260902_rls_guc_guard` — rewrites 21 policy predicates, adopts `controlled_documents` + `controlled_document_versions` (23 total)
  - `20260903_app_lp_role` — `CREATE ROLE qgp_app` + grants + `ALTER DEFAULT PRIVILEGES`
- **Workflows/jobs/queues (if any):** none
- **Config/env/flags:** none. The runtime DSN is untouched.
- **Dependencies (added/removed/updated):** none

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Inert-by-construction. A `rolbypassrls` role never evaluates a policy, so rewriting 23 predicates is a no-op for the current application identity. `qgp_app` cannot log in.
- **Tolerant reader / strict writer applied?** Yes, and this is the substance of the change. The old predicate `tenant_id = current_setting('app.current_tenant_id', true)::int` failed **loud**, not closed. The new one, `tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int`, fails closed.
- **Breaking changes:** none while the app keeps bypassing RLS. Changing the role without completing CUT-2 is a total authentication outage — see §"what breaks" below.
- **Migration plan:** both migrations run under the existing admin credential, as the whole chain already does. Both verify their own result via `pg_policy` / `pg_roles` and raise if reality disagrees. Both are PostgreSQL-only and no-op on other dialects.
- **Rollback strategy (DB):** both have real `downgrade()` paths. `20260902` restores the previous bare-cast predicate and drops the two adopted policies; `20260903` revokes grants and default privileges. Neither downgrade touches data.

### What I verified, versus what I inferred
Production is firewalled and I did not reach it. **Nothing below was measured against production.**

**Verified** — by building a database from the full 215-migration chain on PostgreSQL 14 and interrogating `pg_policy` / `pg_class` / `information_schema`:
- 21 tables carried `tenant_isolation`, all with `relrowsecurity` **and** `relforcerowsecurity`, all with `USING` and `WITH CHECK` of `tenant_id = current_setting('app.current_tenant_id', true)::int`.
- The GUC is `app.current_tenant_id`. There is no `app.tenant_id` anywhere in the codebase — the name in the brief does not exist.
- `set_config(name, value, true)` reverts to the **empty string**, not to unset, on COMMIT, on ROLLBACK and on `DISCARD ALL`. `''::int` raises SQLSTATE 22P02. Reproduced through the application's own `create_async_engine` + pool.
- `controlled_documents` and `controlled_document_versions` had **no RLS at all**, despite `RLS_TABLES` listing them.
- Of the 21 policy tables, only `users` and `workflow_rules` have a nullable `tenant_id` on a freshly migrated schema.
- `init_db()` runs only when `settings.is_development`, so the production app needs no `CREATE`.
- `session_replication_role = replica` does **not** relax RLS.

**Inferred, and requiring confirmation before any cutover:**
- That the production app role is in fact `qgpadmin`. The runtime DSN comes from Key Vault and is not in the repo; `qgpadmin` appears in `infra/main.bicep` as the *administrator login*.
- Which policy tables hold NULL `tenant_id` **in production**. The `NOT NULL` constraints above were applied by *data-conditional* migrations that skip when rows are non-conforming, so production may still permit NULL where a fresh database does not. `scripts/ops/run026/rls_role_readiness.py` measures this.

### Correction to the brief — the stated blast radius is wrong
The brief says ~1,696 tenant-less rows across 23 tables would vanish, led by `vehicle_defects` (623), `vehicle_registry` (362), `audit_responses` (313), `audit_questions` (118).

**None of those four tables has an RLS policy.** RLS applies only where it is enabled, so a tenant-less row in a table with no policy is entirely unaffected by the role change. The real blast radius is the *intersection* of "has a policy" and "holds NULL `tenant_id`" — on a fresh schema, `users` and `workflow_rules` only. Those 1,696 rows are still a real problem (C-01/TEN2), but they are **not** what gates this change. Two things do, and neither is about data:

1. **The predicate failed loud, not closed** (fixed here). On a *pooled* connection that had already served one tenant-scoped request, a later tenant-less request would not have returned an empty list — it would have returned HTTP 500 and poisoned the rest of the transaction. Load-dependent, so it would have passed a smoke test and failed under traffic.
2. **Authentication cannot resolve a tenant** (NOT fixed — this is the blocker). `users` is under FORCE RLS, but auth reads it *before* the tenant is known, because the tenant is a column on the row being fetched (`auth_service.py:72` by email, `dependencies/__init__.py:92` by id). The JWT carries no tenant claim. Measured: `qgp_app` sees **0 of 2** users with no GUC bound. No backfill fixes this; it is the shape of the code.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Every `tenant_isolation` predicate treats an empty GUC as "no tenant" and filters, rather than raising 22P02 — verified on all 23 policies
- [x] AC-02: `RLS_TABLES` describes reality — the 2 registry tables with no policy now have one; 23 deployed, 23 registered, no drift either way
- [x] AC-03: `qgp_app` exists with exactly the DML privileges the app needs, holds no `BYPASSRLS`/`SUPERUSER`/`CREATEDB`/`CREATEROLE`/`REPLICATION`, cannot `TRUNCATE`, and has no credential
- [x] AC-04: Cross-tenant reads and cross-tenant writes are both refused under `qgp_app` on all 23 policy tables
- [x] AC-05: An operator can measure production readiness without mutating anything (`rls_role_readiness.py`, read-only, no `--apply` path exists)
- [x] AC-06: The auth-bootstrap blocker is asserted by a test, so the cutover cannot be attempted while it stands without a test going red
- [x] AC-07: Ordering requirement and blast radius documented for the product owner

## 5) Testing Evidence (link to runs)
- [x] Lint — `black` and `isort` clean (local)
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_run026_rls_least_privilege.py`, **15 passed** (local). No database required; these parse the migrations with `ast` and assert the design properties directly.
- [x] Integration tests — `tests/integration/test_run026_rls_least_privilege_postgres.py`, **12 passed** against PostgreSQL 14 at the new head (local)
- [x] Regression check — full integration suite at the new head: **803 passed, 5 skipped, 4 xpassed, 0 failed** (137s, local PostgreSQL 14). Run on a clean database at the *old* head, the only failures were the new tests above, which is the point.
- [ ] Contract tests — N/A (no API surface)
- [ ] E2E Smoke — N/A. The app cannot yet run as `qgp_app`; that is CUT-2.

**These tests fail today.** Verified by running them against a clean database at the previous head (`20260901_case_tenant_nn`): the predicate tests fail on all 21 policies, the registry test fails on the 2 unprotected tables, and the role tests fail because `qgp_app` does not exist.

**Policies actually exercised: 23 of 23** (the 21 that existed, plus the 2 that should have). Not merely inspected — each one was seeded with a row for two tenants and then read and written as `qgp_app` via `SET LOCAL ROLE`, with tenant A bound. The isolation test asserts that *no* policy table was left unseeded, so a table that could not be exercised fails the run rather than quietly reducing coverage.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01 (tenant isolation under the future role):** with tenant A bound, `qgp_app` sees its own row and none of tenant B's, on all 23 policy tables; and an `UPDATE` moving a row to tenant B is rejected by `WITH CHECK` on all 23
- [x] **CUJ-02 (pooled connection with no tenant bound):** a connection that has already served a tenant-scoped transaction returns **zero rows** on the next tenant-less query instead of raising 22P02. This is the journey that was broken and is the reason this PR exists ahead of the role change.
- [x] CUJ-03 (existing behaviour unaffected): full integration suite green at the new head — the app still bypasses RLS, so nothing here is live yet
- [ ] **CUJ-04 (login) — KNOWN BROKEN under the new role, and deliberately left red.** `test_authentication_is_still_the_blocking_gate` asserts `qgp_app` sees 0 users with no tenant bound. It passes today because auth *is* broken under the new role. When CUT-2 lands it will fail, and that failure is the signal to invert it.

## 7) Observability & Ops
- **Logs:** both migrations log what they changed and how many tables they touched, at INFO
- **Metrics:** none added. Post-cutover, the signal to watch is 500s carrying `invalid input syntax for type integer: ""` (should now be impossible) and `permission denied for table`.
- **Alerts:** none added. Note that the CUT-3 failure mode — background jobs silently processing zero rows — produces **no error and no alert**, which is why it is a sequenced prerequisite and not a post-deploy check.
- **Runbook updates:** `docs/governance/rls-least-privilege-rollout.md` (new); preflight is `python -m scripts.ops.run026.rls_role_readiness --json`

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** apply both migrations, then run the readiness script as an admin role. Expect exit 1 with the auth bootstrap named as the blocker — that is the correct result today, not a failure of this PR.
- **Canary plan:** N/A for this PR (inert). The *role change* itself, later, is not canary-able in the usual sense: it is a connection-string change with a binary blast radius, so it goes to staging and soaks there first.
- **Prod post-deploy checks:** confirm 23 policies carry `NULLIF` and both `relrowsecurity`/`relforcerowsecurity`; confirm `qgp_app` exists with `rolcanlogin = false` and `rolbypassrls = false`. No application behaviour should change at all.

### The ordering requirement (the important part)
Each step must be complete and verified before the next begins. These `CUT-n` steps are **not** the repo's release Gate 0–5 below; they are the cutover sequence for this change.

| Step | What | Status |
|---|---|---|
| CUT-0 | `qgp_app` created with grants, no credential | **done, this PR** |
| CUT-1 | Every predicate survives an empty GUC; the 2 unprotected tables adopted | **done, this PR** |
| CUT-2 | Authentication can resolve a tenant without already having one | **BLOCKED — not started** |
| CUT-3 | Every background / cross-tenant path audited for an unbound GUC | not started |
| CUT-4 | NULL `tenant_id` remediated or explicitly excepted, **in policy tables only** | not started |
| CUT-5 | Staging cutover; readiness script clean; soak | not started |
| CUT-6 | Production cutover, human-authorised | not started |

**What breaks if the sequence is not followed:**
- **Skipping CUT-2** — total authentication outage. Nobody can log in; every existing token 401s. Recovery is reverting the connection string.
- **Skipping CUT-1** — intermittent HTTP 500s on whichever requests land on a recycled connection. Load-dependent; would pass a smoke test.
- **Skipping CUT-3** — Celery tasks and cross-tenant sweeps silently process **zero rows**, with no error and no alert. `training_matrix_upload_reminder_tasks.py:153`, `regulatory_watch_actions.py:108`, `action_service.py:254`.
- **Skipping CUT-4** — a tenant-less `users` row means that account is permanently locked out; a tenant-less `workflow_rules` row means that automation silently stops firing.
- **Missing a grant** — `permission denied for table X` on first access. `ALTER DEFAULT PRIVILEGES` only covers objects created by the role that set it, so if the migration identity ever changes, new tables arrive ungranted. The readiness script checks every table and every sequence for exactly this.

### Role design
Two roles; only the application's identity changes.

**`qgp_app`** — runtime identity. `NOLOGIN`, no password, `NOBYPASSRLS`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`. Granted `CONNECT`, `USAGE` on `public`, `SELECT, INSERT, UPDATE, DELETE` on all tables, `USAGE, SELECT` on all sequences, and the same by default on future objects. Deliberately **not** granted `TRUNCATE`, `REFERENCES`, `TRIGGER` or `CREATE` — `TRUNCATE` matters most, because PostgreSQL has no per-row TRUNCATE check, so a role holding it can empty a tenant-scoped table across *every* tenant regardless of `tenant_isolation`. Granting it `LOGIN` and a Key Vault password is a runbook step, so no credential exists in version control.

**Migrations keep the existing admin credential, unchanged.** `20260901_case_tenant_nn` already *refuses to run* without `rolsuper`/`rolbypassrls`, because `COUNT(*) WHERE tenant_id IS NULL` returns 0 under FORCE RLS while the `SET NOT NULL` heap scan still aborts — data-repair migrations must see every row. The chain also issues `CREATE EXTENSION` and `CREATE ROLE`. `qgp_migrations` (`NOLOGIN BYPASSRLS`) exists for this and is left alone: giving it `LOGIN` would create a second privileged credential to rotate *and* change the deployment path in the same change as the RLS switch-on.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** any unexpected change in application behaviour after deploy (there should be none), or `alembic check` / migration verification failing
- **Rollback steps:** `alembic downgrade 20260901_case_tenant_nn`, which restores the previous predicates on all 21 tables, drops the 2 adopted policies, and revokes `qgp_app`'s grants and default privileges. No data is touched by either direction. `qgp_app` itself is left in place by `downgrade()` and is harmless (`NOLOGIN`, no password); drop it manually if desired. Reverting the PR alone is also safe, since the app bypasses RLS regardless.
- **Owner:** Lane LEASTPRIV (RUN-026); production role change authorised separately by David

## 10) Evidence Pack (links)
- CI run(s): linked on this PR after open
- Staging deploy evidence: N/A — nothing to observe; this change is inert by construction
- Canary evidence (if applicable): N/A

### What remains untested
- **Anything against production or staging.** Every measurement is from a local PostgreSQL 14 database built by the real migration chain.
- **The application running end-to-end as `qgp_app`.** Policies, grants and role attributes are proven; a full request path under the new role is not, and cannot be until CUT-2 lands.
- **PostgreSQL 16**, which CI uses and Azure may run. The empty-string GUC revert was verified on 14 only. The integration test asserts that behaviour explicitly, so CI will tell us if 16 differs.
- **Query-plan impact of `NULLIF` on large tables.** Still a stable once-per-query expression, so index quals on `tenant_id` should be unaffected — but not benchmarked.
- **Whether production's policy tables actually contain NULL `tenant_id`.** Only the readiness script, run against production, can answer that.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Data/migration contracts — no schema change; both migrations self-verify and have real downgrades
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — expected result is readiness script exit 1 naming the auth blocker
- [ ] **Gate 4:** N/A (canary not applicable to an inert change)
- [ ] **Gate 5:** Production verification plan + monitoring ready — plan in §8; **the role change itself is explicitly NOT authorised by this PR**

## Exclusive allowlist (this PR)
- `alembic/versions/20260902_rls_empty_guc_guard.py`
- `alembic/versions/20260903_app_least_privilege_role.py`
- `src/infrastructure/middleware/tenant_context.py` (two constants + comments; no behaviour change)
- `scripts/ops/run026/__init__.py`
- `scripts/ops/run026/rls_role_readiness.py`
- `tests/unit/test_run026_rls_least_privilege.py`
- `tests/integration/test_run026_rls_least_privilege_postgres.py`
- `docs/governance/rls-least-privilege-rollout.md`
- `scripts/governance/pr_body_run026_leastpriv.md`

**Forbidden / not touched:** the connection string or any Key Vault secret; `qgp_app` `LOGIN`; the authentication path; any `tenant_id` backfill; any existing test; other lanes' worktrees; `/tmp/qgp-merge-allowlist`.
