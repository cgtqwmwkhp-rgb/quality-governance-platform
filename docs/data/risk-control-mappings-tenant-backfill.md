# risk_control_mappings tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from parent `risks_v2` via `risk_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_rcm_tenant_nn` (revises `20260711_bow_tenant_nn`)
- Backfill + align mismatches to parent, then conditional `NOT NULL`.

## Readiness SQL
```sql
SELECT COUNT(*) AS null_mappings
FROM risk_control_mappings
WHERE tenant_id IS NULL;

SELECT COUNT(*) AS null_via_null_parent
FROM risk_control_mappings m
JOIN risks_v2 r ON r.id = m.risk_id
WHERE m.tenant_id IS NULL AND r.tenant_id IS NULL;
```

## Create path
- API and service stamp `tenant_id=risk.tenant_id` when linking a control.
