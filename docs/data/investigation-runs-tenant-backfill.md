# Investigation runs tenant backfill (WCS-TEN2 / C-01 Phase 2)

## Scope

Single table family only: `investigation_runs.tenant_id`, inherited from
`investigation_templates` via the NOT NULL FK `investigation_runs.template_id`.

Do **not** invent `tenant_id=1`. Parent `investigation_templates.tenant_id` may still be
NULL (shared/catalog templates); those run rows stay NULL until the template is
attributed or the run is stamped at create time.

## Migration `20260710_ir_tenant_nn`

1. Backfill NULL runs from the parent template when `investigation_templates.tenant_id IS NOT NULL`.
2. Align mismatches so the run matches the template when the template is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULLs.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning, leave nullable, and **succeed** (deploy must not fail).

`InvestigationTemplate.tenant_id` stays nullable. Risks / incidents / complaints cores
remain out of scope for this revision.

## Readiness checks

```sql
SELECT count(*) AS null_runs
FROM investigation_runs
WHERE tenant_id IS NULL;

SELECT count(*) AS null_parent_blocks
FROM investigation_runs AS r
JOIN investigation_templates AS t ON t.id = r.template_id
WHERE r.tenant_id IS NULL AND t.tenant_id IS NULL;

SELECT count(*) AS mismatches
FROM investigation_runs AS r
JOIN investigation_templates AS t ON t.id = r.template_id
WHERE r.tenant_id IS DISTINCT FROM t.tenant_id
  AND t.tenant_id IS NOT NULL;
```

## Rollback

Downgrade restores `investigation_runs.tenant_id` to nullable when it was NOT
NULL. Attribution data is kept.
