# enterprise_risk_controls tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from control owner `users` via `control_owner_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_erc_tenant_nn` (revises `20260711_rah_tenant_nn`)
- Backfill + align mismatches to owner, then conditional `NOT NULL`.

## Readiness SQL
```sql
SELECT COUNT(*) AS null_controls
FROM enterprise_risk_controls
WHERE tenant_id IS NULL;
```

## Create path
- `POST /controls` stamps `tenant_id=current_user.tenant_id`.
