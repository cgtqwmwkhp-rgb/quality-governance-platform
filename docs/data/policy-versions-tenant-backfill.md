# policy_versions tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from parent `policies` via `policy_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_pv_tenant_nn` (revises `20260711_erc_tenant_nn`)

## Create path
- No live `PolicyVersion(...)` write API yet; when added, stamp `tenant_id=policy.tenant_id`.
