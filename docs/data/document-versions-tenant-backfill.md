# document_versions tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from parent `documents` via `document_id`.
- Never invent `tenant_id=1`.
- Fail-safe: Alembic only enforces `NOT NULL` when residual NULL count is 0.

## Migration
- Revision: `20260711_dv_tenant_nn` (revises `20260711_doc_tenant_nn`)

## Create path
- Version writes should stamp `tenant_id=document.tenant_id` (or caller tenant).
