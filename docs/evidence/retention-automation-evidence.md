# Data Retention Automation Evidence (D07)

Documentation of automated data retention enforcement mechanisms.

## Retention Policies

| Data Category | Retention Period | Enforcement | Evidence |
|---------------|-----------------|-------------|----------|
| Audit trail entries | 7 years | Database archival job (planned) | `src/domain/services/audit_log_service.py` |
| Evidence assets (Blob) | Governed by lifecycle policy | Azure Blob lifecycle rules | `docs/infra/cost-controls.md` §2.3 |
| Session tokens (JWT) | 24 hours | Token expiry in auth service | `src/domain/services/auth_service.py` |
| Rate limit counters | 1 hour | Redis TTL | `src/infrastructure/middleware/rate_limiter.py` |
| Telemetry buffer | 100 events max | Client-side buffer cap | `frontend/src/services/telemetry.ts` |
| GDPR data exports | 30 days | Manual process (automated planned) | `src/domain/services/gdpr_service.py` |

## Azure Blob Lifecycle Rules

Configured in Azure Portal and documented in `docs/infra/cost-controls.md`:

- **Hot → Cool**: After 90 days of no access
- **Cool → Archive**: After 365 days of no access
- **Delete**: Not auto-deleted (manual review required for compliance)

## GDPR Compliance

| Right | Implementation | Automation Status |
|-------|---------------|-------------------|
| Right to Access (SAR) | Export endpoint | Semi-automated |
| Right to Erasure | Soft delete + purge | Semi-automated |
| Right to Rectification | Standard CRUD | Automated |
| Data Portability | JSON export | Semi-automated |

## Related Documents

- [`docs/compliance/gdpr-compliance.md`](../compliance/gdpr-compliance.md) — GDPR compliance
- [`docs/infra/cost-controls.md`](../infra/cost-controls.md) — storage lifecycle policies
- [`src/domain/services/gdpr_service.py`](../../src/domain/services/gdpr_service.py) — GDPR service
