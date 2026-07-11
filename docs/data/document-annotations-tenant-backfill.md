# Document annotations tenant backfill (WCS-TEN2)

## Purpose

Fail-safe backfill of `document_annotations.tenant_id` from parent `documents`
via `document_id`, then conditional `NOT NULL` only when residual NULLs are zero.
Never invent `tenant_id=1`.

## Migration

- Revision: `20260711_dann_tenant_nn`
- Revises: `20260711_dal_tenant_nn` (after document_distributions / #733)
- File: `alembic/versions/20260711_document_annotations_tenant_not_null.py`

## Readiness checks

```sql
SELECT COUNT(*) FROM document_annotations WHERE tenant_id IS NULL;
SELECT COUNT(*) FROM document_annotations a
LEFT JOIN documents d ON d.id = a.document_id
WHERE a.tenant_id IS NULL OR d.tenant_id IS NULL;
```

## Rollback

`alembic downgrade 20260711_dal_tenant_nn` restores nullable `tenant_id`.
