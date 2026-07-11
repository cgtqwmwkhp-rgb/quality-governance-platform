# document_access_logs tenant_id backfill (WCS-TEN2)

## Policy
- Inherit `tenant_id` from `controlled_documents` via `document_id`.
- Never invent `tenant_id=1`.
- Fail-safe: NOT NULL only when residual NULL count is 0.

## Migration
- Revision: `20260711_dal_tenant_nn` (revises `20260711_odr_tenant_nn`)
