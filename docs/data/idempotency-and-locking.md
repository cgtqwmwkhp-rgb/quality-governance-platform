# Data Integrity: Idempotency & Locking (D24)

Documentation of data integrity mechanisms in the Quality Governance Platform.

## Idempotency

### Current Implementation

| Mechanism | Location | Scope |
|-----------|----------|-------|
| Redis-based idempotency keys | `src/infrastructure/middleware/rate_limiter.py` | POST/PUT/PATCH requests |
| Database unique constraints | Model definitions | Reference number uniqueness |
| External audit import dedup | `ExternalAuditImportJob` model | `uq_external_audit_import_job_idempotency` |

### Redis Fallback Behavior

When Redis is unavailable:
1. Idempotency checking is **skipped** (fail-open)
2. A warning is logged: `"Redis unavailable, idempotency check skipped"`
3. Database unique constraints serve as the last line of defense
4. Duplicate reference numbers are caught by `UniqueConstraint` and return 409 Conflict

**Rationale**: Fail-open is preferred over fail-closed to maintain availability. The database constraints prevent actual data corruption even without Redis.

## Optimistic Locking

### Current Implementation

| Model | Mechanism | Column |
|-------|-----------|--------|
| `InvestigationRun` | Version column | `version` |
| Other models | `updated_at` comparison | `updated_at` |

### Optimistic Locking Pattern

```python
# Check version before update
if existing.version != expected_version:
    raise HTTPException(409, "Record modified by another user")
existing.version += 1
```

### Expansion Plan

| Phase | Models | Mechanism |
|-------|--------|-----------|
| Phase 1 (current) | `InvestigationRun` | Explicit `version` column |
| Phase 2 | `AuditRun`, `EnterpriseRisk` | Add `version` column |
| Phase 3 | All mutable domain models | Standardized `VersionMixin` |

## Transaction Management

| Pattern | Usage | Evidence |
|---------|-------|----------|
| Request-scoped DB session | All API handlers | `get_async_session` dependency |
| Explicit commit on success | Service layer | `session.commit()` in service methods |
| Automatic rollback on exception | Error handling | SQLAlchemy session context manager |
| Statement timeout | Query protection | `statement_timeout=30000` in `database.py` |

## Related Documents

- [`src/infrastructure/database.py`](../../src/infrastructure/database.py) — session management
- [`src/infrastructure/middleware/rate_limiter.py`](../../src/infrastructure/middleware/rate_limiter.py) — rate limiting + idempotency
- [`src/domain/models/investigation.py`](../../src/domain/models/investigation.py) — optimistic locking example
