# Service Level Objectives (SLOs)

## Platform SLOs

| SLO | Target | Measurement | Alert Threshold |
|-----|--------|------------|-----------------|
| Availability | 99.9% | Successful health checks / total checks | < 99.5% |
| API Latency (p95) | < 500ms | p95 response time across all endpoints | > 750ms |
| API Latency (p99) | < 2000ms | p99 response time across all endpoints | > 3000ms |
| Error Rate | < 1% | 5xx responses / total responses | > 2% |
| Login Success Rate | > 99% | Successful logins / login attempts | < 98% |
| Data Integrity | 100% | Audit log completeness for CRUD operations | Any gap |

## Per-Endpoint SLOs

| Endpoint Group | p95 Latency | Error Budget |
|---------------|-------------|--------------|
| /api/v1/incidents | 300ms | 0.5% |
| /api/v1/audits | 500ms | 0.5% |
| /api/v1/reports | 2000ms | 1.0% |
| /api/v1/documents | 1000ms | 0.5% |
| /api/v1/auth | 200ms | 0.1% |

## Error Budget Policy

- **Budget**: 0.1% monthly (43.2 minutes downtime)
- **Warning**: 50% budget consumed → review scheduled
- **Critical**: 80% budget consumed → feature freeze, focus on reliability
- **Exhausted**: 100% consumed → incident review, mandatory improvements before new features

## Measurement Windows

- **Availability**: Rolling 30-day window
- **Latency**: Rolling 7-day window
- **Error Rate**: Rolling 24-hour window

## Escalation Matrix

| Budget Consumed | Action | Owner |
|----------------|--------|-------|
| 50% | Email alert to team | SRE Lead |
| 80% | PagerDuty alert, daily standup review | Engineering Manager |
| 100% | Incident review, deploy freeze | VP Engineering |
