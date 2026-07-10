# Document-control tenant backfill

## Phase 1 deployment

`20260710_doc_ctl_tenant` keeps `tenant_id` nullable to make deployment
additive and avoid a table rewrite or long-running validation lock. The
migration repairs missing columns/indexes and copies tenant ownership from
`controlled_documents` into document versions, approvals, distributions,
training links, access logs, and obsolete records where the parent is already
attributed.

Application reads now require an authenticated tenant and use an exact
`tenant_id` match. Null legacy rows are therefore quarantined rather than
visible to every tenant. New parent and child rows receive the authenticated
tenant ID at creation.

## Root-row attribution

Before enforcing `NOT NULL`, operators must map the remaining root rows:

1. Export counts grouped by table where `tenant_id IS NULL`.
2. Attribute `controlled_documents` using authoritative ownership data
   (document register, author/owner membership, or an approved customer
   mapping). Do not infer a default tenant.
3. Attribute `document_approval_workflows` from the owning organisation's
   approved workflow register.
4. Re-run the parent-to-child updates from the migration after root rows are
   assigned.
5. Investigate any child whose tenant differs from its parent; do not overwrite
   conflicts until ownership is confirmed.

Example readiness checks:

```sql
SELECT 'controlled_documents' AS table_name, count(*) AS null_tenants
FROM controlled_documents WHERE tenant_id IS NULL
UNION ALL
SELECT 'document_approval_workflows', count(*)
FROM document_approval_workflows WHERE tenant_id IS NULL;

SELECT count(*) AS mismatched_versions
FROM controlled_document_versions AS child
JOIN controlled_documents AS parent ON parent.id = child.document_id
WHERE child.tenant_id IS DISTINCT FROM parent.tenant_id;
```

## Phase 2 constraint rollout

After the null count and mismatch count are both zero in every environment:

1. Add and validate foreign keys to `tenants(id)` using the database's
   low-lock procedure.
2. Add temporary `CHECK (tenant_id IS NOT NULL) NOT VALID` constraints and
   validate them online.
3. Set each column `NOT NULL`, then remove temporary checks.
4. Add composite tenant/identifier uniqueness where business keys must only be
   unique inside a tenant. In particular, review the current global
   `controlled_documents.document_number` uniqueness before changing it.

Rollback of Phase 1 is an application rollback. Keep the nullable columns and
attribution data; dropping them would discard ownership evidence.
