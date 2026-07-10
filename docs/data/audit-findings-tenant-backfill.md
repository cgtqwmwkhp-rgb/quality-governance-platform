# Audit findings tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `audit_findings.tenant_id`, inherited from
`audit_runs` via the NOT NULL FK `audit_findings.run_id`.

Do **not** invent `tenant_id=1`. Parent `audit_runs.tenant_id` may still be
NULL; those child rows stay NULL until the parent is attributed.

## Migration `20260710_af_tenant_nn`

1. Backfill NULL findings from the parent run when `audit_runs.tenant_id IS NOT NULL`.
2. Align mismatches so the child matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`AuditRun.tenant_id` stays nullable. Incidents / risks / complaints are out of
scope for this revision.

## Readiness checks

```sql
SELECT count(*) AS null_findings
FROM audit_findings
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM audit_findings AS f
JOIN audit_runs AS r ON r.id = f.run_id
WHERE f.tenant_id IS NULL AND r.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM audit_findings AS f
JOIN audit_runs AS r ON r.id = f.run_id
WHERE f.tenant_id IS DISTINCT FROM r.tenant_id
  AND r.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `audit_findings.tenant_id` to nullable when it was NOT NULL.
Attribution data is kept.
