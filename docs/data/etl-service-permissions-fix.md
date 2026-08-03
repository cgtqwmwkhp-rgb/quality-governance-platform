# `roles.permissions` for the `etl-service` role (C-65)

> **BLOCKED — no statement in this document has been run, and none should be run
> until `etl-service` has a named owner.** The encoding is unambiguously wrong.
> What the role is *for* is not, and the two candidate repairs differ by two
> permissions that have never actually worked, one of which is
> `incident:set_reference_number`. Choosing between them changes what a live
> integration is allowed to do, so it is an ownership decision, not a repair.
>
> Board id `w1-etl-service-lossy-encoding`, handed to business ownership in
> [#1522](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/issues/1522):
> *"Name an owner for `etl-service` before permission-encoding repair proceeds."*

**Status: NOT APPLIED** to staging or production. Nothing in the repository
executes any statement below — no Alembic revision, no seed, no startup hook.

| Environment | Encoding observed | Repair | Verified |
| --- | --- | --- | --- |
| Staging | `postgres_array_literal` — `{incident:create,incident:view_all,incident:set_reference_number}` | **NOT APPLIED** — blocked, see above | — |
| Production | not enumerated for this role; run Step 1 before assuming it is absent | **NOT APPLIED** | — |

This is the sibling of
[`admin-role-permissions-grant.md`](./admin-role-permissions-grant.md), which
covers the wildcard row on the `admin` role. Read the encoding table in that
document's Step 1 first; this one does not repeat it.

## Defect

`roles.permissions` for `etl-service` holds a **PostgreSQL array literal** where
a JSON array is expected:

```text
{incident:create,incident:view_all,incident:set_reference_number}
```

`User.has_permission` (`src/domain/models/user.py`) calls `json.loads` on the
column and, on `JSONDecodeError`, falls back to splitting on commas. That
fallback is what makes this encoding dangerous rather than merely wrong: the
braces stay attached to the outermost tokens, so the role parses as

```text
["{incident:create", "incident:view_all", "incident:set_reference_number}"]
```

and the permission check — which is exact set-membership, with no glob, prefix or
expansion anywhere on the path — matches only the middle one.

| Token as written | Token as parsed | Granted today |
| --- | --- | --- |
| `incident:create` | `{incident:create` | **no** |
| `incident:view_all` | `incident:view_all` | yes |
| `incident:set_reference_number` | `incident:set_reference_number}` | **no** |

This is asserted, not inferred:
`tests/unit/test_permission_validation.py::test_postgres_array_literal_loses_exactly_its_outer_tokens`
runs this exact string through the real `User.has_permission` and pins all three
outcomes. `src.domain.authz.describe_stored_permissions` reports the same thing
without a database.

**Why this is the worst of the three bad encodings.** A role that plainly grants
nothing (the `admin` wildcard) produces an immediate, total, obvious failure. A
role that works for its middle permissions and silently fails for its outermost
two produces an intermittent one, and it fails *asymmetrically*: this role can
see every tenant's incidents (`incident:view_all`) and cannot create one
(`incident:create`), which is the opposite of least privilege and the opposite of
what an import service is for. An access review reading the column sees three
plausible tokens and no defect.

## Why the repair is blocked, and not merely unscheduled

Nothing in this repository creates a role named `etl-service`.
`src/api/routes/testing.py` creates **`etl_user`** — a different name, with a
different and larger token list (`complaint:create`, `complaint:read`,
`incident:create`, `incident:read`, `rta:create`, `rta:read`), written correctly
with `json.dumps`. So the intended grant for `etl-service` cannot be derived from
the code the way `ADMIN_ROLE_PERMISSIONS` derives the admin grant. There is no
authoritative list to converge on.

That leaves two repairs, and they are not equivalent:

**Repair A — preserve the written intent.** Re-encode the same three tokens as a
JSON array. The stored value then means what whoever wrote it appears to have
meant. This *grants two permissions that have never worked*:

- `incident:create` — plausible for an import service, and the reason the role
  probably exists.
- `incident:set_reference_number` — one of the two families deliberately withheld
  even from the `admin` role, because it allows overriding a generated reference
  number. Turning it on for an unattended integration is a decision about
  traceability of incident records, and this document is not the place it gets
  made.

**Repair B — preserve the effective permissions.** Re-encode only the token that
actually works today, `incident:view_all`. Nothing any caller can do changes.
This is the null-risk option, and it is also the one that leaves a
tenant-wide read grant as the entire content of a service role, which is very
unlikely to be what anyone wants.

Neither is derivable from the code, so both are guesses without an owner. Repair
A is written out below because it is the one that will be wanted if the role is
still in use; Repair B is written out because it is the one to apply if the role
turns out to be debris that cannot yet be deleted.

**A third outcome is likely and is not covered by either statement:** if Step 1
shows the role is attached to no user, the answer is to delete it, the way the
eleven test-debris roles were deleted under C-10. That is also an ownership
decision and it needs no encoding repair at all.

## Step 1 — diagnose, read-only

Run all four queries. The first three take no locks and modify nothing.

**1a. Every role, with its apparent encoding.** Do not filter to `etl-service`:
the point of enumerating is to find the roles nobody has mentioned.

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

**1b. Who holds it — the blast radius of any repair.** A repair that grants
`incident:create` grants it to every account this returns.

```sql
SELECT r.id            AS role_id,
       r.name          AS role_name,
       count(ur.user_id) AS holder_count,
       array_agg(u.email ORDER BY u.email) FILTER (WHERE u.email IS NOT NULL) AS holders,
       bool_or(u.is_superuser) AS any_holder_is_superuser,
       bool_or(u.is_active)    AS any_holder_is_active
FROM roles r
LEFT JOIN user_roles ur ON ur.role_id = r.id
LEFT JOIN users u       ON u.id = ur.user_id
WHERE r.name = 'etl-service'
GROUP BY r.id, r.name;
```

`holder_count = 0` means no repair is urgent and deletion is on the table.
`any_holder_is_superuser = true` means the encoding is irrelevant for that
holder: `User.has_permission` returns `True` for a superuser *before* it reads
any role, so a superuser proves nothing about whether this fix worked.

**1c. Confirm the exact stored bytes before writing a `WHERE` clause against
them.** The guarded statements below match on the literal value, so a trailing
space or a different token order makes them a no-op — which is the intended
failure mode, but only if you know that is why.

```sql
SELECT id,
       name,
       length(permissions)             AS byte_length,
       md5(permissions)                AS value_md5,
       permissions
FROM roles
WHERE name = 'etl-service';
```

For the staging value quoted at the top of this document, expect
`byte_length = 65` and `value_md5 = 8012ba1a2493e94f26d17cfa1ac5e8a1`. That pair
was computed on PostgreSQL 16.14 as
`SELECT md5('{incident:create,incident:view_all,incident:set_reference_number}')`,
against the string the unit test pins — not read from a live database, because
this document has not touched one. **Recompute it in your own session** rather
than trusting the value here. If it differs, the stored value is not the one the
statements below were written for, and neither of them applies.

**1d. Explain it without a database.** For any row 1a flags:

```python
from src.domain.authz import describe_stored_permissions

describe_stored_permissions("{incident:create,incident:view_all,incident:set_reference_number}")
```

## Step 2 — Repair A: re-encode the three written tokens (needs owner sign-off)

**Do not run without an owner's decision recorded in this document.** This grants
`incident:create` and `incident:set_reference_number`, neither of which works
today.

```sql
BEGIN;

UPDATE roles
SET permissions = '["incident:create", "incident:set_reference_number", "incident:view_all"]'
WHERE name = 'etl-service'
  AND permissions = '{incident:create,incident:view_all,incident:set_reference_number}';

-- Verify UPDATE 1 before continuing. Anything else means the row is not in the
-- state this statement was written for: ROLLBACK and re-run Step 1.
COMMIT;   -- or ROLLBACK;
```

**Rows affected: exactly the `roles` rows named `etl-service` whose
`permissions` is still literally the observed array literal.** Expect
`UPDATE 1`. The `WHERE` clause names the old value, so a re-run after a
successful repair is a no-op rather than an overwrite, and a re-run after someone
else has corrected the row differently leaves their value alone.

The tokens are sorted and lower-cased because that is what
`canonicalise_permissions_input` produces, so the row matches what the API write
path would now store. Sorting changes the stored shape and not its meaning:
`has_permission` compares stripped, lower-cased tokens for set membership.

## Step 2b — Repair B: re-encode only the permission that works (no privilege change)

Apply this one if the role must keep working exactly as it does today — for
instance, if it is in use and its owner has not yet decided.

```sql
BEGIN;

UPDATE roles
SET permissions = '["incident:view_all"]'
WHERE name = 'etl-service'
  AND permissions = '{incident:create,incident:view_all,incident:set_reference_number}';

-- Verify UPDATE 1.
COMMIT;   -- or ROLLBACK;
```

Effective permissions before and after are identical, which is the entire
argument for it. It is not a fix for the role, only for the encoding, and it
leaves the question of what `etl-service` should be able to do exactly where
Step 1 found it — so record it here as an interim measure with a date, not as a
closure.

## Step 3 — verify

```sql
SELECT name,
       json_array_length(permissions::json) AS token_count,
       permissions LIKE '%*%'               AS contains_wildcard,
       permissions LIKE '{%'                AS still_pg_array_literal,
       permissions::jsonb ? 'incident:create'                AS has_incident_create,
       permissions::jsonb ? 'incident:view_all'              AS has_incident_view_all,
       permissions::jsonb ? 'incident:set_reference_number'  AS has_set_reference_number
FROM roles
WHERE name = 'etl-service';
```

After Repair A: `token_count = 3`, `still_pg_array_literal = false`, all three
`has_*` true. After Repair B: `token_count = 1`, `has_incident_view_all = true`,
the other two false.

`json_array_length` will itself error if the column is still an array literal, so
a failure here is a result and not a broken query.

Then confirm the effect at the boundary, because the column being right is not
the same as the integration working. Sign in as (or issue a token for) a
**non-superuser** holder returned by 1b, and — after Repair A only — `POST` one
incident through the API path the importer uses. A superuser proves nothing:
`has_permission` short-circuits on the flag before it reads the role.

## Rollback

```sql
UPDATE roles
SET permissions = '{incident:create,incident:view_all,incident:set_reference_number}'
WHERE name = 'etl-service';
```

This restores the lossy encoding exactly, including its two dead tokens. It is
offered only so the change is reversible on paper. After Repair A it is a genuine
revocation of `incident:create` and `incident:set_reference_number`; after Repair
B it changes no effective permission and only reinstates the misleading value.

## Why this cannot recur through the API

`src/api/schemas/user.py` applies `canonicalise_permissions_input` to the role
request schemas, which rejects a PostgreSQL array literal with a 422 and names it
as silently lossy in the error. That guard landed in PR #1399. It covers the API
write path only — a direct `UPDATE`, including the ones above, is validated by
nothing.

Two paths that are not covered and should be checked before this is called
closed:

- `src/api/routes/testing.py` writes the `etl_user` role with `json.dumps` and
  does **not** go through `canonicalise_permissions_input`. Its six tokens are
  all catalogued, so it is correct today by construction rather than by
  validation. It is staging-only and gated on `X-CI-Secret`.
- No migration or seed writes `roles.permissions` at all, and nothing anywhere
  writes a role named `etl-service`. Whatever created it did so outside this
  repository, which is the same gap as the missing owner.

## What would close C-65

1. A named owner for `etl-service`.
2. That owner's answer to: is the role in use, and by what?
3. Either a deletion, or Repair A/B applied with the outcome and date recorded in
   the table at the top of this document.
4. If the role is to stay, its intended token list belongs in
   `src/domain/authz/catalogue.py` beside `ADMIN_ROLE_PERMISSIONS`, so that the
   next person can derive it from code instead of reading a live column — which is
   the actual root cause of this defect and the only step that stops the next one.
