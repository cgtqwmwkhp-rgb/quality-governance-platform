# controlled_documents tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from `users` via `author_id`, then `owner_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_cd_tenant_nn` (revises `20260711_cdv_tenant_nn`)

## Create path
- `create_document` already stamps `tenant_id=tenant_id` from the current user.
