# risk_assessment_history tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from parent `risks_v2` via `risk_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_rah_tenant_nn` (revises `20260711_kri_tenant_nn`)
- Backfill + align mismatches to parent, then conditional `NOT NULL`.

## Readiness SQL
```sql
SELECT COUNT(*) AS null_history
FROM risk_assessment_history
WHERE tenant_id IS NULL;
```

## Create path
- `_record_assessment` stamps `tenant_id=risk.tenant_id`.
