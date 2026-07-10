# RTA actions tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `rta_actions.tenant_id`, inherited from
`road_traffic_collisions` via the NOT NULL FK `rta_actions.rta_id`.

Do **not** invent `tenant_id=1`. Parent `road_traffic_collisions.tenant_id` may still be
NULL; those child rows stay NULL until the parent is attributed.

## Migration `20260710_rta_act_nn`

1. Backfill NULL actions from the parent RTA when `road_traffic_collisions.tenant_id IS NOT NULL`.
2. Align mismatches so the child matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`RoadTrafficCollision.tenant_id` stays nullable. Parent cores (incidents / risks /
complaints) are out of scope for this revision.

## Readiness checks

```sql
SELECT count(*) AS null_actions
FROM rta_actions
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM rta_actions AS a
JOIN road_traffic_collisions AS r ON r.id = a.rta_id
WHERE a.tenant_id IS NULL AND r.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM rta_actions AS a
JOIN road_traffic_collisions AS r ON r.id = a.rta_id
WHERE a.tenant_id IS DISTINCT FROM r.tenant_id
  AND r.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `rta_actions.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
