# External audit import drafts tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `external_audit_import_drafts.tenant_id`, inherited from
`external_audit_import_jobs` via the NOT NULL FK `external_audit_import_drafts.import_job_id`.

Do **not** invent `tenant_id=1`. Parent `external_audit_import_jobs.tenant_id` may still be
NULL (fail-safe path); those draft rows stay NULL until the parent job is attributed
or the draft is stamped at create time.

## Migration `20260710_ext_draft_nn`

1. Backfill NULL drafts from the parent import job when `external_audit_import_jobs.tenant_id IS NOT NULL`.
2. Align mismatches so the draft matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

Create paths stamp `tenant_id` from the parent import job (never invent a default).

## Readiness checks

```sql
SELECT count(*) AS null_drafts
FROM external_audit_import_drafts
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM external_audit_import_drafts AS p
JOIN external_audit_import_jobs AS r ON r.id = p.import_job_id
WHERE p.tenant_id IS NULL AND r.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM external_audit_import_drafts AS p
JOIN external_audit_import_jobs AS r ON r.id = p.import_job_id
WHERE p.tenant_id IS DISTINCT FROM r.tenant_id
  AND r.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `external_audit_import_drafts.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
