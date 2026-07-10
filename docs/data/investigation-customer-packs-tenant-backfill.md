# Investigation customer packs tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `investigation_customer_packs.tenant_id`, inherited from
`investigation_runs` via the NOT NULL FK `investigation_customer_packs.investigation_id`.

Do **not** invent `tenant_id=1`. Parent `investigation_runs.tenant_id` may still be
NULL (fail-safe path); those pack rows stay NULL until the parent run is attributed
or the pack is stamped at create time.

## Migration `20260710_inv_pack_nn`

1. Backfill NULL packs from the parent investigation run when `investigation_runs.tenant_id IS NOT NULL`.
2. Align mismatches so the pack matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

Create paths stamp `tenant_id` from the parent investigation (never invent a default).

## Readiness checks

```sql
SELECT count(*) AS null_packs
FROM investigation_customer_packs
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM investigation_customer_packs AS p
JOIN investigation_runs AS r ON r.id = p.investigation_id
WHERE p.tenant_id IS NULL AND r.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM investigation_customer_packs AS p
JOIN investigation_runs AS r ON r.id = p.investigation_id
WHERE p.tenant_id IS DISTINCT FROM r.tenant_id
  AND r.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `investigation_customer_packs.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
