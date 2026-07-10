# Complaint actions tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `complaint_actions.tenant_id`, inherited from
`complaints` via the NOT NULL FK `complaint_actions.complaint_id`.

Do **not** invent `tenant_id=1`. Parent `complaints.tenant_id` may still be
NULL; those child rows stay NULL until the parent is attributed.

## Migration `20260710_ca_tenant_nn`

1. Backfill NULL actions from the parent complaint when `complaints.tenant_id IS NOT NULL`.
2. Align mismatches so the child matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`Complaint.tenant_id` stays nullable. Risks / incidents / audit_runs are out of
scope for this revision.

## Readiness checks

```sql
SELECT count(*) AS null_actions
FROM complaint_actions
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM complaint_actions AS a
JOIN complaints AS c ON c.id = a.complaint_id
WHERE a.tenant_id IS NULL AND c.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM complaint_actions AS a
JOIN complaints AS c ON c.id = a.complaint_id
WHERE a.tenant_id IS DISTINCT FROM c.tenant_id
  AND c.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `complaint_actions.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
