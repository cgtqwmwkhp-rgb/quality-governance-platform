# Data Integrity: Idempotency & Locking (D24)

Documentation of data integrity mechanisms in the Quality Governance Platform.

## Idempotency

### Current Implementation

| Mechanism | Location | Scope |
|-----------|----------|-------|
| Redis-based idempotency keys | `src/api/middleware/idempotency.py` | POST/PUT/PATCH requests |
| Database unique constraints | Model definitions | Reference number uniqueness |
| External audit import dedup | `ExternalAuditImportJob` model | `uq_external_audit_import_job_idempotency` |

### Redis Fallback Behavior

When Redis is unavailable:
1. Idempotency checking is **skipped** (fail-open)
2. A debug message is logged: `"Idempotency middleware: Redis unavailable, processing request normally"`
3. Database unique constraints serve as the last line of defense
4. Duplicate reference numbers are caught by `UniqueConstraint` and return 409 Conflict

**Rationale**: Fail-open is preferred over fail-closed to maintain availability. The database constraints prevent actual data corruption even without Redis.

## Fail-Open Threat Model

### Redis Availability SLO

- **Target**: 99.9% availability (Azure Cache for Redis Basic/Standard SLA)
- **Monitoring metric**: `idempotency.fail_open.count` — incremented each time the middleware skips idempotency due to Redis unavailability
- **Alerting threshold**: > 5 fail-open events per minute triggers a **P2 incident** (investigate Redis connectivity, check Azure service health)

### Risk per Route Category

| Route category | Examples | Risk when fail-open | DB backstop | Quantified risk |
|----------------|----------|---------------------|-------------|-----------------|
| **Safe (read-only)** | GET endpoints | None — reads are inherently idempotent | N/A | No risk |
| **Low-risk (creates with unique constraint)** | Incident creation, audit trail entries, status updates | Potential duplicate POST accepted by middleware | `UniqueConstraint` on `reference_number` returns 409 Conflict | < 0.1% of requests during Redis outage could see transient 409 |
| **Medium-risk (updates without version check)** | Bulk status transitions, batch imports | Duplicate PUT/PATCH may re-apply same mutation | `updated_at` comparison or idempotent field assignments | Negligible — same-state writes are no-ops at DB level |
| **Higher-risk (financial/payment)** | Not present in QGP | N/A | N/A | N/A — QGP has no payment mutations |

### Accepted Risk Rationale

QGP is a governance platform, not a payment system. Database uniqueness constraints serve as a backstop when Redis idempotency is skipped. The combination of 99.9% Redis availability and database-level constraints reduces the probability of user-visible duplicate data to < 0.01% annualised.

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
- [`src/api/middleware/idempotency.py`](../../src/api/middleware/idempotency.py) — idempotency middleware
- [`src/infrastructure/middleware/rate_limiter.py`](../../src/infrastructure/middleware/rate_limiter.py) — rate limiting
- [`src/domain/models/investigation.py`](../../src/domain/models/investigation.py) — optimistic locking example
