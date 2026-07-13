# Near misses tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `near_misses.tenant_id` (PARENT core), inherited from
`users` via `near_misses.created_by_id`.

`near_misses` is a parent core Safety CUJ entity (sibling to `incidents` and
`road_traffic_collisions`). For legacy NULL parent rows, the most reliable
attribution path is through the creating user's tenant membership (same pattern
as `incidents`).

Do **not** invent `tenant_id=1`. Creator `users.tenant_id` may still be NULL,
and portal/anonymous intake rows may lack `created_by_id`; those near-miss rows
stay NULL until attributed at create time or via a follow-up.

## Migration `20260713_nm_tenant_nn`

1. Backfill NULL near misses from the creator user when `users.tenant_id IS NOT NULL`.
2. Align mismatches so the near miss matches the creator when the creator is attributed
   (`IS DISTINCT FROM` + creator non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`User.tenant_id` stays nullable. Child runner-sheet entries (`near_miss_running_sheet_entries`)
remain out of scope for this revision.

Create paths stamp `tenant_id` from the authenticated user / configured portal
tenant (never invent a silent default of `1`).

## Readiness checks

```sql
SELECT count(*) AS null_near_misses
FROM near_misses
WHERE tenant_id IS NULL;

SELECT count(*) AS null_creator_blocks
FROM near_misses AS nm
JOIN users AS u ON u.id = nm.created_by_id
WHERE nm.tenant_id IS NULL AND u.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM near_misses AS nm
JOIN users AS u ON u.id = nm.created_by_id
WHERE nm.tenant_id IS DISTINCT FROM u.tenant_id
  AND u.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `near_misses.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
