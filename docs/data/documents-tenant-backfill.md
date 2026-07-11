# documents tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from `users` via `created_by_id`, then `reviewed_by_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_doc_tenant_nn` (revises `20260711_pol_tenant_nn`)

## Create path
- Document create already stamps `tenant_id=current_user.tenant_id`.
