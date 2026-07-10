# Investigation actions tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `investigation_actions.tenant_id`, inherited from
`investigation_runs` via the NOT NULL FK `investigation_actions.investigation_id`.

Do **not** invent `tenant_id=1`. Parent `investigation_runs.tenant_id` may still be
NULL; those action rows stay NULL until the parent run is attributed.

## Migration `20260710_inv_act_nn`

1. Backfill NULL actions from the parent investigation run when `investigation_runs.tenant_id IS NOT NULL`.
2. Align mismatches so the action matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`InvestigationRun.tenant_id` stays nullable. Parent cores remain out of scope.

## Readiness checks

```sql
SELECT count(*) AS null_actions
FROM investigation_actions
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM investigation_actions AS a
JOIN investigation_runs AS r ON r.id = a.investigation_id
WHERE a.tenant_id IS NULL AND r.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM investigation_actions AS a
JOIN investigation_runs AS r ON r.id = a.investigation_id
WHERE a.tenant_id IS DISTINCT FROM r.tenant_id
  AND r.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `investigation_actions.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
