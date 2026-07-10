# External audit import jobs tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `external_audit_import_jobs.tenant_id`, inherited from
`audit_runs` via the NOT NULL FK `external_audit_import_jobs.audit_run_id`.

Do **not** invent `tenant_id=1`. Parent `audit_runs.tenant_id` may still be
NULL (fail-safe path); those job rows stay NULL until the parent run is attributed
or the job is stamped at create time.

## Migration `20260710_external_audit_import_jobs_tenant_nn`

1. Backfill NULL jobs from the parent audit run when `audit_runs.tenant_id IS NOT NULL`.
2. Align mismatches so the job matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

Create paths stamp `tenant_id` from the parent audit run (never invent a default).

## Readiness checks

```sql
SELECT count(*) AS null_jobs
FROM external_audit_import_jobs
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM external_audit_import_jobs AS p
JOIN audit_runs AS r ON r.id = p.audit_run_id
WHERE p.tenant_id IS NULL AND r.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM external_audit_import_jobs AS p
JOIN audit_runs AS r ON r.id = p.audit_run_id
WHERE p.tenant_id IS DISTINCT FROM r.tenant_id
  AND r.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `external_audit_import_jobs.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
