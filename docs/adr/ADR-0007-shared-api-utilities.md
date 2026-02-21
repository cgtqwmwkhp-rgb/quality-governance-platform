# ADR-0007: Shared API Utilities — Pagination, Entity Lookup, Update Patterns

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

Across the platform's 47 route files, common patterns were duplicated extensively: manual pagination with inconsistent parameter names (`per_page`, `size`, `page_size`), repetitive entity-lookup-or-404 blocks, and boilerplate partial-update logic. This duplication led to inconsistent API behavior, increased bug surface area, and made refactoring pagination or error handling a multi-file effort.

## Decision

We extract shared utilities into `src/api/utils/` with three focused modules. `pagination.py` provides a `paginate()` function that standardizes offset/limit calculation and response envelope formatting using a consistent `page_size` parameter. `entity.py` provides `get_or_404()` for tenant-scoped entity lookup with proper error responses. `update.py` provides `apply_partial_update()` for safe dictionary-based partial updates with field validation.

## Consequences

### Positive
- Eliminates hundreds of lines of duplicated code across route files
- Ensures consistent pagination behavior and parameter naming across all endpoints
- Bug fixes to lookup or update patterns propagate automatically to all routes
- New route files can be built faster by composing shared utilities

### Negative
- Adds a layer of indirection that developers must understand before modifying API behavior
- Shared utilities become a coupling point — changes affect all consumers simultaneously

### Neutral
- Existing tests must be updated to reflect the new utility function signatures
- Route files become significantly shorter and more focused on business-specific logic
