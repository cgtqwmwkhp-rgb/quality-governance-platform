# Runbook: Platform Incident Response

**Owner**: Platform Engineering
**Last Updated**: 2026-03-07
**Review Cycle**: Quarterly

---

## 1. Trigger Conditions

- Azure Monitor alert fires for SLO breach (availability < 99.9%, error rate > 1%, P95 > 500ms)
- Health probe failures on `/readyz` (503 responses)
- DLQ depth exceeds threshold (> 10 items)
- Circuit breaker opens on any external integration
- Customer-reported outage or data integrity issue
- Security incident (unauthorized access, data breach indicator)

## 2. Severity Classification

| Severity | Criteria | Response Time | Escalation |
|----------|----------|--------------|------------|
| **SEV-1** | Platform fully unavailable; data integrity breach; security compromise | 15 min | Immediate — engineering lead + CTO |
| **SEV-2** | Major feature degraded; >10% error rate; auth failures | 30 min | Within 1 hour — engineering lead |
| **SEV-3** | Minor feature impact; single tenant affected; performance degradation | 2 hours | Next business day |
| **SEV-4** | Cosmetic; non-blocking; workaround available | Best effort | N/A |

## 3. Immediate Actions (First 15 Minutes)

1. **Acknowledge** — Confirm alert in monitoring channel; assign incident commander
2. **Assess scope** — Check:
   - `/readyz` endpoint status
   - Azure Monitor dashboard for error patterns
   - Recent deployments (last 4 hours)
   - Recent config/secret changes
3. **Communicate** — Post in #incidents channel: severity, impact, who is investigating
4. **Contain** — If deployment-related:
   - Consider immediate rollback (see `rollback.md`)
   - If config change, revert Key Vault secret and restart

## 4. Diagnostic Steps

### 4.1 Application Health
```
GET /healthz        → Is the process alive?
GET /readyz         → Is the database connected?
GET /api/v1/meta/version  → Which build is deployed?
```

### 4.2 Database
- Check connection pool: Azure Monitor → `db.pool_size`, `db.pool_overflow`
- Check slow queries: Azure Monitor → `db.query_duration_ms` P95
- Check migration status: `alembic current` on ACI container

### 4.3 External Dependencies
- Azure AD: Can token exchange succeed? Check circuit breaker state
- Redis: Is Celery processing tasks? Check `celery.dlq_depth`
- Azure Blob Storage: Can evidence files be uploaded?

### 4.4 Rate Limiting
- Check `rate_limit.exceeded` counter — is a client being throttled legitimately?
- Check for DDoS patterns in access logs

## 5. Resolution Procedures

### Database Connection Failure
1. Verify PostgreSQL is running: Azure Portal → Database status
2. Check network connectivity between App Service and PostgreSQL
3. If pool exhaustion: restart application (forces pool recreation)
4. If database is down: trigger database recovery runbook (`database-recovery.md`)

### Deployment Regression
1. Identify last successful build SHA from deploy evidence
2. Execute rollback: see `rollback.md`
3. Root cause via git diff between current and last-good SHA

### Authentication Failure
1. Check Azure AD service health
2. Verify JWKS cache: force refresh by restarting app
3. If JWT secret rotation needed: update in Key Vault, restart app

## 6. Post-Incident

1. **Update status** — Confirm resolution in #incidents
2. **Write post-mortem** — Within 48 hours: timeline, root cause, impact, action items
3. **Create action items** — Tickets for preventive measures
4. **Update runbook** — Incorporate any new diagnostic steps learned
5. **Review SLO impact** — Calculate error budget consumption

## 7. Contacts

| Role | Name | Contact |
|------|------|---------|
| Engineering Lead | David Harris | david.harris@plantexpand.com |
| Platform On-Call | Rotating (see on-call schedule below) | #incidents Slack channel |
| CTO (SEV-1 only) | David Harris | david.harris@plantexpand.com |
| Azure Support | N/A | Azure Portal → Support |

### On-Call Rotation

The platform on-call rotation operates on a **weekly cycle** (Monday 09:00 to Monday 09:00 UTC).

| Week | Primary | Secondary |
|------|---------|-----------|
| Odd weeks | Engineering Lead | Platform Engineer |
| Even weeks | Platform Engineer | Engineering Lead |

**Escalation outside business hours**: Post in the #incidents Slack channel and use @oncall mention. If no response within 15 minutes for SEV-1, contact the Engineering Lead directly via phone.
