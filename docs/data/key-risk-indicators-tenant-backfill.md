# key_risk_indicators tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from parent `risks_v2` via `risk_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_kri_tenant_nn` (revises `20260711_rcm_tenant_nn`)
- Backfill + align mismatches to parent, then conditional `NOT NULL`.

## Readiness SQL
```sql
SELECT COUNT(*) AS null_kris
FROM key_risk_indicators
WHERE tenant_id IS NULL;
```

## Create path
- `POST /kris` stamps `tenant_id=risk.tenant_id`.
