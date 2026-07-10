# Incident actions tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `incident_actions.tenant_id`, inherited from
`incidents` via the NOT NULL FK `incident_actions.incident_id`.

Do **not** invent `tenant_id=1`. Parent `incidents.tenant_id` may still be
NULL; those child rows stay NULL until the parent is attributed.

## Migration `20260710_ia_tenant_nn`

1. Backfill NULL actions from the parent incident when `incidents.tenant_id IS NOT NULL`.
2. Align mismatches so the child matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`Incident.tenant_id` stays nullable. Audit findings / risks / complaints are
out of scope for this revision.

## Readiness checks

```sql
SELECT count(*) AS null_actions
FROM incident_actions
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM incident_actions AS a
JOIN incidents AS i ON i.id = a.incident_id
WHERE a.tenant_id IS NULL AND i.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM incident_actions AS a
JOIN incidents AS i ON i.id = a.incident_id
WHERE a.tenant_id IS DISTINCT FROM i.tenant_id
  AND i.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `incident_actions.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
