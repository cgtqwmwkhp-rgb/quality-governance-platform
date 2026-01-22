# Observability and Alerting Runbook

**Version:** 1.0  
**Date:** 2026-01-22  
**Owner:** Platform SRE Team

## Overview

This document defines the observability stack, alerting rules, and incident response procedures for the Quality Governance Platform.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
├─────────────────────────────────────────────────────────────┤
│  FastAPI App  │  Structured Logs  │  Metrics  │  Traces    │
│               │  (JSON format)    │  (APM)    │  (Req ID)  │
└───────────────┴───────────────────┴───────────┴────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Azure Monitor                            │
├─────────────────────────────────────────────────────────────┤
│  Application Insights  │  Log Analytics  │  Alert Rules    │
└───────────────────────────────────────────────────────────────┘
```

## Structured Logging

### Log Format

All application logs are emitted as JSON with the following fields:

```json
{
  "timestamp": "2026-01-22T19:30:00.000Z",
  "level": "INFO",
  "logger": "src.api.routes.incidents",
  "message": "Incident created",
  "request_id": "abc-123-def",
  "user_id": "user-456",
  "module": "incidents",
  "function": "create_incident",
  "lineno": 45,
  "extra": {
    "incident_id": "INC-2026-0001",
    "severity": "high"
  }
}
```

### Key Fields

| Field | Purpose | PII Safe? |
|-------|---------|-----------|
| `request_id` | Correlation across services | ✅ Yes |
| `user_id` | User attribution (UUID only) | ✅ Yes |
| `level` | Log severity | ✅ Yes |
| `module` | Source code location | ✅ Yes |
| `extra` | Structured metadata | ⚠️ Depends on content |

### PII Guidelines

- **NEVER** log: passwords, tokens, full emails, PII
- **ALLOWED**: user IDs (UUIDs), reference numbers, timestamps
- **MASK**: email domains only (user@***.com)

## Metrics

### Application Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `http_requests_total` | Counter | Total HTTP requests | N/A (baseline) |
| `http_request_duration_seconds` | Histogram | Request latency | P95 > 2s |
| `http_requests_5xx_total` | Counter | 5xx error count | > 10/min |
| `http_requests_401_total` | Counter | Auth failures | > 100/min |
| `rate_limit_hits_total` | Counter | Rate limit triggers | > 1000/min |
| `db_query_duration_seconds` | Histogram | DB query latency | P95 > 500ms |
| `migration_status` | Gauge | 1=success, 0=failed | = 0 |

### Health Metrics

| Endpoint | Check | Frequency | Timeout |
|----------|-------|-----------|---------|
| `/healthz` | Process alive | 10s | 5s |
| `/readyz` | DB connected | 30s | 10s |

## Alert Rules

### Critical Alerts (Page Immediately)

#### ALERT-001: High 5xx Error Rate

```yaml
name: High5xxErrorRate
condition: rate(http_requests_5xx_total[5m]) > 10
severity: critical
runbook: "#alert-001-response"
action: Page on-call engineer immediately
```

**Response Steps:**
1. Check application logs for error stack traces
2. Check database connectivity: `GET /readyz`
3. Check recent deployments in GitHub Actions
4. Rollback if deployment-related: `az webapp deployment slot swap`

#### ALERT-002: Migration Failure

```yaml
name: MigrationFailure
condition: migration_status == 0 for 5m
severity: critical
runbook: "#alert-002-response"
action: Block deployment pipeline
```

**Response Steps:**
1. Check migration logs in Azure Container Instance
2. Review failed migration: `alembic history`
3. Fix migration script and redeploy
4. Never manually modify production database

#### ALERT-003: Health Check Failure

```yaml
name: HealthCheckFailure
condition: probe_success{endpoint="/healthz"} == 0 for 3m
severity: critical
runbook: "#alert-003-response"
action: Page on-call engineer
```

**Response Steps:**
1. Check Azure App Service status
2. Restart app: `az webapp restart`
3. Check container logs: `az webapp log tail`
4. Escalate if restart fails

### Warning Alerts (Notify Slack)

#### ALERT-004: Elevated Auth Failures

```yaml
name: ElevatedAuthFailures
condition: rate(http_requests_401_total[5m]) > 50
severity: warning
runbook: "#alert-004-response"
action: Notify #platform-alerts Slack channel
```

**Response Steps:**
1. Check for brute force patterns in logs
2. Verify Azure AD configuration
3. Check for expired tokens/certificates
4. Consider temporary rate limit reduction

#### ALERT-005: High Rate Limit Hits

```yaml
name: HighRateLimitHits
condition: rate(rate_limit_hits_total[5m]) > 500
severity: warning
runbook: "#alert-005-response"
action: Notify #platform-alerts Slack channel
```

**Response Steps:**
1. Identify source IPs/users from logs
2. Check for legitimate traffic spike
3. Consider temporary allowlist for known clients
4. Review rate limit configuration

#### ALERT-006: Elevated Latency

```yaml
name: ElevatedLatency
condition: histogram_quantile(0.95, http_request_duration_seconds) > 2
severity: warning
runbook: "#alert-006-response"
action: Notify #platform-alerts Slack channel
```

**Response Steps:**
1. Check database query performance
2. Review recent code changes
3. Check Azure resource utilization
4. Scale up if resource-constrained

## SLO Definitions

| SLO | Target | Measurement Window | Error Budget |
|-----|--------|-------------------|--------------|
| Availability | 99.9% | 30 days | 43 minutes/month |
| Latency P95 | < 2s | 30 days | 5% of requests |
| Error Rate | < 0.1% | 30 days | 0.1% of requests |

### SLO Burn Rate Alerts

```yaml
# Fast burn (1% budget in 1 hour)
name: SLOFastBurn
condition: slo_burn_rate_1h > 14.4
severity: critical

# Slow burn (10% budget in 6 hours)  
name: SLOSlowBurn
condition: slo_burn_rate_6h > 6
severity: warning
```

## Dashboards

### Primary Dashboard: Platform Health

**Panels:**
1. Request Rate (RPS)
2. Error Rate (5xx %)
3. Latency P50/P95/P99
4. Active Users
5. Database Connections
6. Container CPU/Memory

### Secondary Dashboard: Security

**Panels:**
1. Auth Success/Failure Rate
2. Rate Limit Hits
3. Suspicious IP Activity
4. Failed Login Attempts

## Log Queries

### Find Errors for Request ID

```kusto
AppTraces
| where Properties.request_id == "abc-123-def"
| order by TimeGenerated desc
```

### 5xx Errors in Last Hour

```kusto
AppRequests
| where ResultCode startswith "5"
| where TimeGenerated > ago(1h)
| summarize count() by bin(TimeGenerated, 5m), ResultCode
```

### Slowest Endpoints

```kusto
AppRequests
| where TimeGenerated > ago(1h)
| summarize P95=percentile(DurationMs, 95) by Name
| order by P95 desc
| take 10
```

### Auth Failures by IP

```kusto
AppRequests
| where ResultCode == "401"
| where TimeGenerated > ago(1h)
| summarize count() by ClientIP
| order by count_ desc
| take 20
```

## Escalation Matrix

| Severity | Response Time | Escalation Path |
|----------|--------------|-----------------|
| Critical | 5 minutes | On-call → Team Lead → CTO |
| Warning | 30 minutes | On-call → Team Lead |
| Info | Next business day | Triage in standup |

## On-Call Rotation

- Primary: Platform Engineer (weekly rotation)
- Secondary: Senior Engineer (backup)
- Escalation: Engineering Manager

## Incident Post-Mortem Template

```markdown
# Incident Report: [TITLE]

## Summary
- **Duration:** X hours Y minutes
- **Impact:** Z users affected
- **Severity:** Critical/Warning

## Timeline
- HH:MM - Alert triggered
- HH:MM - Engineer acknowledged
- HH:MM - Root cause identified
- HH:MM - Mitigation applied
- HH:MM - Incident resolved

## Root Cause
[Description]

## Resolution
[Steps taken]

## Action Items
- [ ] Item 1 (Owner, Due Date)
- [ ] Item 2 (Owner, Due Date)

## Lessons Learned
[What we learned]
```

## References

- [Azure Monitor Documentation](https://docs.microsoft.com/azure/azure-monitor/)
- [Application Insights](https://docs.microsoft.com/azure/azure-monitor/app/app-insights-overview)
- [SRE Workbook](https://sre.google/workbook/table-of-contents/)
