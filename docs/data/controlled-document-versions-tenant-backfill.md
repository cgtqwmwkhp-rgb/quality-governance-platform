# controlled_document_versions tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from parent `controlled_documents` via `document_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_cdv_tenant_nn` (revises `20260711_pv_tenant_nn`)

## Create path
- Document create/version routes stamp `tenant_id=tenant_id` (caller tenant).
