# Incidents tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `incidents.tenant_id` (PARENT core), inherited from
`users` via `incidents.created_by_id`.

`incidents` is a parent core entity. Child `incident_actions` already inherit
from this table. For legacy NULL parent rows, the most reliable attribution
path is through the creating user's tenant membership (same pattern as
`capa_actions`).

Do **not** invent `tenant_id=1`. Creator `users.tenant_id` may still be NULL,
and portal/anonymous intake rows may lack `created_by_id`; those incident rows
stay NULL until attributed at create time or via a follow-up.

## Migration `20260710_inc_tenant_nn`

1. Backfill NULL incidents from the creator user when `users.tenant_id IS NOT NULL`.
2. Align mismatches so the incident matches the creator when the creator is attributed
   (`IS DISTINCT FROM` + creator non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`User.tenant_id` stays nullable. Sibling parent cores (`complaints`, `risks`,
`risks_v2`) remain out of scope for this revision.

Create paths stamp `tenant_id` from the authenticated user / configured portal
tenant (never invent a silent default of `1`).

## Readiness checks

```sql
SELECT count(*) AS null_incidents
FROM incidents
WHERE tenant_id IS NULL;

SELECT count(*) AS null_creator_blocks
FROM incidents AS i
JOIN users AS u ON u.id = i.created_by_id
WHERE i.tenant_id IS NULL AND u.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM incidents AS i
JOIN users AS u ON u.id = i.created_by_id
WHERE i.tenant_id IS DISTINCT FROM u.tenant_id
  AND u.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `incidents.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
