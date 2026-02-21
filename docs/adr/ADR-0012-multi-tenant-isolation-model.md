# ADR-0012: Multi-Tenant Data Isolation via Row-Level Filtering

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

The Quality Governance Platform serves multiple organizations (tenants) from a single deployment. Each tenant's data — incidents, audits, documents, risks — must be strictly isolated to prevent cross-tenant data leakage. A data breach where one tenant sees another's compliance records would be catastrophic for trust and potentially violate regulatory requirements. The isolation mechanism must be reliable, performant, and difficult to accidentally bypass.

## Decision

We implement row-level tenant isolation using a `tenant_id` column on all tenant-scoped database tables. Every API endpoint that accesses tenant data includes a `verify_tenant_access` FastAPI dependency that extracts the tenant from the authenticated user's JWT token and injects it as a query filter. All database queries for tenant-scoped data are automatically filtered by `tenant_id`. Superuser accounts can bypass tenant filtering for cross-tenant administrative operations.

## Consequences

### Positive
- Simple, well-understood isolation model with no additional infrastructure required
- Tenant filtering is enforced at the API layer via dependency injection, reducing bypass risk
- Single database simplifies operations, backups, and migrations compared to database-per-tenant
- Superuser bypass enables platform-wide reporting and administration

### Negative
- Every tenant-scoped table must include a `tenant_id` column — schema discipline is required
- A bug in the tenant filtering dependency could expose cross-tenant data
- Query performance depends on proper indexing of `tenant_id` columns
- No database-level isolation — a SQL injection could potentially cross tenant boundaries

### Neutral
- Tenant isolation is tested via dedicated integration tests that verify cross-tenant query prevention
- The pattern requires all new routes to explicitly declare tenant scope via the dependency
- Database-per-tenant remains a future option if regulatory requirements demand stronger isolation
