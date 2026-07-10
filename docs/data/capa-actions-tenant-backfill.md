# CAPA actions tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `capa_actions.tenant_id`, inherited from
`users` via the NOT NULL FK `capa_actions.created_by_id`.

Unlike other action tables (incident_actions, complaint_actions, rta_actions),
`capa_actions` is a standalone CAPA record without a single parent entity FK.
The most reliable attribution path is through the creating user's tenant
membership.

Do **not** invent `tenant_id=1`. Creator `users.tenant_id` may still be
NULL; those CAPA rows stay NULL until the creator is attributed.

## Migration `20260710_capa_act_nn`

1. Backfill NULL actions from the creator user when `users.tenant_id IS NOT NULL`.
2. Align mismatches so the CAPA matches the creator when the creator is attributed
   (`IS DISTINCT FROM` + creator non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`User.tenant_id` stays nullable. Parent cores (incidents / risks /
complaints) are out of scope for this revision.

## Readiness checks

```sql
SELECT count(*) AS null_capas
FROM capa_actions
WHERE tenant_id IS NULL;

SELECT count(*) AS null_creator_blocks
FROM capa_actions AS c
JOIN users AS u ON u.id = c.created_by_id
WHERE c.tenant_id IS NULL AND u.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM capa_actions AS c
JOIN users AS u ON u.id = c.created_by_id
WHERE c.tenant_id IS DISTINCT FROM u.tenant_id
  AND u.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `capa_actions.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
