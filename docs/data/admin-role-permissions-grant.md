# `roles.permissions` for the admin role (C-1)

**Status: APPLIED to staging and production, 29 July 2026.** Nothing in the repository
executes any statement below — no Alembic revision, no seed, no startup hook — so applying
it remains a human decision, and it was taken by David Harris. Each environment needed a
*different* statement, which is the part to read before reusing this document.

| Environment | Applied | Statement used | Verified |
|---|---|---|---|
| Staging | 29 Jul, ~12:50 UTC | the `UPDATE` in Step 2 | `token_count = 75`, `contains_wildcard = false`, and a **non-superuser** admin then loaded `/incidents/`, `/complaints/` and `/near-misses/` |
| Production | 29 Jul, 18:19 UTC | an **`INSERT`**, not the `UPDATE` | role `id=13`, 75 tokens, no wildcard, `is_system_role = true`, `tenant_id NULL`, **no user assigned** |

**Why production needed an `INSERT`.** Step 2's `UPDATE` assumes a row already holding
`'["*"]'`. Production's `roles` table was **completely empty** — 0 rows, and 0 in
`user_roles` — because the eleven test-debris roles were deleted under C-10 and nothing was
provisioned afterwards. So there was no wildcard row to correct. That emptiness was a defect
in its own right (**C-72**): production ran entirely on the `is_superuser` flag, and because
`User.has_permission` returns `True` for a superuser *before* it reads any role, every
authorisation check added by C-2 would have been a no-op for superusers and a hard lockout
for anyone else.

**The grant written to production was cross-checked, not retyped.** It was derived from
`ADMIN_ROLE_PERMISSIONS` in `src/domain/authz/catalogue.py`, asserted at 75 tokens with no
wildcard before the write, and compared token-for-token against the value **already applied
and proven in staging**. They matched exactly, so production received the value known to
work rather than a fresh interpretation of this document. The insert and the C-72 user change
ran in one transaction with each statement's affected-row count asserted at exactly 1, and
verification ran afterwards on a fresh connection so it could not read its own uncommitted
state.

**The production role is deliberately unassigned.** `user_roles` holds 0 rows. It exists so a
real administrator can be provisioned against a documented grant; granting it to an existing
account was explicitly declined, because the only active non-superuser was a dormant account
with no demonstrated need, and that account was deactivated instead.

**Two tokens are absent from this grant on purpose.** `action:read` and `risk:read` are in
`RESERVED_PERMISSIONS`, not `ENFORCED_PERMISSIONS`, and `ADMIN_ROLE_PERMISSIONS` derives from
the latter. Promoting either is not a one-line change: it grows this grant to 77 tokens, makes
this document stale, fails `tests/unit/test_admin_grant_statement.py`, and the new grant then
has to be applied by hand to every environment before the corresponding endpoint can be gated.

> **If you are reading this because a PR wants to gate an endpoint on a permission:** check the
> token is in the table above *and* that the grant has been applied in the environment you are
> shipping to. This document said "NOT APPLIED" for several hours after staging had in fact been
> updated, and a lane correctly refused to merge on that basis. Re-run Step 3 rather than
> trusting this header.

## Defect

The `admin` role's `roles.permissions` column holds the string `'["*"]'`: a JSON
array containing a wildcard.

`User.has_permission` (`src/domain/models/user.py`) parses that column and does
**exact set-membership** on the tokens it finds. There is no glob, prefix or
expansion anywhere on the path. So a role holding `["*"]` holds one permission
literally named `*`, and no route asks for a permission called `*`. The admin role
therefore grants nothing at all, which is why an authenticated admin sees
permanent skeleton loaders and cannot open the incident, complaint or near-miss
registers: `incident:read`, `complaint:read` and `near_miss:read` all fail.

The wildcard is **not** to be supported. Teaching the checker to expand `*` would
make every future permission automatically granted to whoever holds it, including
permissions that do not exist yet. The fix is an enumerated grant, taken from the
permission catalogue derived from the code
(`src/domain/authz/catalogue.py`, PR #1399).

## Step 1 — diagnose every role first (read-only)

Run this before the update. Production has only a handful of rows, so enumerate
them all rather than sampling; `roles.permissions` is a nullable `TEXT` column that
nothing validated until recently, and three different encodings have been observed
in live databases.

```sql
SELECT id,
       name,
       tenant_id,
       is_system_role,
       permissions,
       CASE
         WHEN permissions IS NULL                                  THEN 'null'
         WHEN btrim(permissions) = ''                               THEN 'empty'
         WHEN btrim(permissions) LIKE '[%]'                         THEN 'json_array'
         WHEN btrim(permissions) LIKE '{%}'                         THEN 'postgres_array_literal'
         ELSE                                                            'bare_comma_separated'
       END                                        AS apparent_encoding,
       permissions LIKE '%*%'                     AS contains_wildcard
FROM roles
ORDER BY id;
```

Encodings and what each does at runtime:

| Stored value | What `has_permission` sees | Effect |
| --- | --- | --- |
| `["a:read", "b:read"]` | `a:read`, `b:read` | correct |
| `["*"]` | `*` | **grants nothing** |
| `a:read,b:read` | `a:read`, `b:read` | works, but unvalidated |
| `{a:read,b:read}` | `{a:read`, `b:read}` | **silently lossy**: `json.loads` fails, the comma split leaves the braces attached, and the role loses exactly its first and last permission while the middle ones work |

The Postgres-array form is the one to look for hardest: a role that half works is
much harder to diagnose than one that plainly does not. For any row the diagnostic
flags, `src.domain.authz.describe_stored_permissions` explains it in the same terms
without touching a database.

## Step 2 — the statement to apply

Restricted to the row actually being fixed, and to the wildcard value actually
observed, so a re-run after someone else has corrected the row is a no-op rather
than an overwrite:

```sql
UPDATE roles
SET permissions = '["action:create", "action:update", "admin:manage", "analytics:create", "analytics:delete", "analytics:manage", "analytics:update", "assessment:create", "assessment:update", "asset:create", "asset:delete", "asset:update", "audit:create", "audit:delete", "audit:read", "audit:update", "capa:create", "capa:update", "complaint:create", "complaint:delete", "complaint:read", "complaint:update", "document:create", "document:read", "document:update", "driver:create", "driver:update", "engineer:create", "engineer:update", "evidence:create", "evidence:update", "form:create", "form:delete", "form:update", "incident:create", "incident:delete", "incident:read", "incident:update", "induction:create", "induction:update", "investigation:approve_customer_omit", "investigation:create", "investigation:delete", "investigation:update", "investigations:comments:read_deleted", "kri:create", "kri:delete", "kri:update", "near_miss:create", "near_miss:delete", "near_miss:read", "near_miss:update", "notifications:delete", "notifications:send", "notifications:update", "policy:create", "policy:delete", "policy:update", "rca:create", "rca:update", "risk:create", "risk:update", "rta:create", "rta:delete", "rta:read", "rta:update", "signature:create", "signature:update", "standard:create", "standard:update", "vehicle:allocate", "vehicle:update", "workflow:create", "workflow:delete", "workflow:update"]'
WHERE name = 'admin'
  AND permissions = '["*"]';
```

**Rows affected: exactly the `roles` rows named `admin` whose `permissions` is
still literally `'["*"]'`.** `roles.name` is `UNIQUE`, so that is at most one row.
Expect `UPDATE 1`. Anything else means the row is not in the state this statement
was written for — stop and re-run Step 1.

Wrap it in a transaction and confirm the count before committing:

```sql
BEGIN;
-- statement above
-- verify UPDATE 1, then:
COMMIT;   -- or ROLLBACK;
```

### What the value is, and what it deliberately omits

75 tokens: every permission the code enforces, minus two families. The list is
`ADMIN_ROLE_PERMISSIONS` in `src/domain/authz/catalogue.py`, and
`tests/unit/test_permission_catalogue.py::test_admin_role_permission_list_is_reviewable`
prints it. `tests/unit/test_admin_grant_statement.py` fails if the statement above
stops matching it, so an approved-then-stale document cannot be applied.

Omitted on purpose (product owner decision, David Harris, Run025):

- `complaint:view_all`, `incident:view_all`, `investigations:view_all`,
  `rta:view_all` — these defeat the own-records-only narrowing that some list
  endpoints apply, turning a scoped list into a tenant-wide one.
- `incident:set_reference_number`, `policy:set_reference_number` — these allow
  overriding a generated reference number.

## Step 3 — verify

```sql
SELECT name,
       json_array_length(permissions::json) AS token_count,
       permissions LIKE '%*%'               AS contains_wildcard
FROM roles
WHERE name = 'admin';
```

Expect `token_count = 75` and `contains_wildcard = false`.

Then confirm the defect is actually gone from the user's point of view, because the
column being right is not the same as the registers loading: sign in as an admin
(not a superuser — `User.has_permission` returns `True` for a superuser before it
reads any role, so a superuser proves nothing here) and open the incident,
complaint and near-miss registers.

## Rollback

```sql
UPDATE roles SET permissions = '["*"]' WHERE name = 'admin';
```

This restores the broken state exactly. It is offered only so the change is
reversible on paper; the prior value granted nothing, so rolling back reinstates
the outage.

## Other roles

Production is reported to hold 3 role rows. Step 1 enumerates all of them; whatever
it returns should be recorded here before Step 2 is applied. Two role definitions
are known from the code and neither needs this fix:

- `etl_user` (`src/api/routes/testing.py`) is written with `json.dumps([...])` and
  its six tokens are all catalogued, so its encoding is already correct. Note that
  this write path does not go through `canonicalise_permissions_input`; it is
  staging-only and gated on `X-CI-Secret`, so it is recorded rather than treated as
  a live risk.
- The integration test fixture's `_ADMIN_PERMS` is a test-only persona and touches
  no deployed database.

## Why this cannot recur through the API

`src/api/schemas/user.py` applies `canonicalise_permissions_input` to the role
request schemas, which rejects the wildcard, unknown tokens, reserved tokens and
every non-JSON-array encoding with a 422. That guard landed in PR #1399 and covers
the API write path only — a direct `UPDATE`, like the one above, is not validated by
anything.
