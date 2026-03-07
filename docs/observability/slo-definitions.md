# SLO/SLI Definitions — Quality Governance Platform

**Owner**: Platform Engineering
**Last Updated**: 2026-03-07
**Review Cycle**: Monthly

---

## Service Level Objectives

### SLO-1: Platform Availability
| Attribute | Value |
|-----------|-------|
| **Target** | 99.9% (43.8 minutes downtime/month) |
| **SLI** | Percentage of successful `/readyz` probe responses (HTTP 200) over a rolling 30-day window |
| **Measurement** | Azure Monitor → custom metric from readiness probe |
| **Error Budget** | 0.1% = ~43 minutes/month |
| **Alert Threshold** | Alert when availability drops below 99.95% over 1-hour window |

### SLO-2: API Latency
| Attribute | Value |
|-----------|-------|
| **Target** | P95 response time < 500ms for all API endpoints |
| **SLI** | 95th percentile of HTTP response duration (excluding file uploads) |
| **Measurement** | Azure Monitor → `api.response_time_ms` histogram, P95 aggregation |
| **Error Budget** | 5% of requests may exceed 500ms |
| **Alert Threshold** | P95 > 500ms sustained for 5 minutes |

### SLO-3: Error Rate
| Attribute | Value |
|-----------|-------|
| **Target** | < 1% server error rate (HTTP 5xx) |
| **SLI** | Count of 5xx responses / total responses, rolling 1-hour window |
| **Measurement** | Azure Monitor → `api.error_rate` counter |
| **Error Budget** | 1% of requests may be 5xx |
| **Alert Threshold** | Error rate > 1% sustained for 5 minutes; > 5% immediate page |

### SLO-4: Authentication Success Rate
| Attribute | Value |
|-----------|-------|
| **Target** | > 99.5% authentication success rate |
| **SLI** | Count of successful auth events / total auth attempts (excluding invalid credentials) |
| **Measurement** | Azure Monitor → `auth.login_success` / (`auth.login_success` + `auth.login_system_error`) |
| **Error Budget** | 0.5% of auth attempts may fail due to system errors |
| **Alert Threshold** | Auth system error rate > 0.5% over 15-minute window |

### SLO-5: Data Write Durability
| Attribute | Value |
|-----------|-------|
| **Target** | Zero data loss on committed writes |
| **SLI** | DLQ depth (should be 0 under normal operation); idempotency conflict rate |
| **Measurement** | Azure Monitor → `celery.dlq_depth`, `data.idempotency_conflict` |
| **Error Budget** | DLQ depth must not exceed 10 items |
| **Alert Threshold** | DLQ depth > 5 for 10 minutes; DLQ depth > 10 immediate page |

---

## SLI Measurement Sources

| SLI | Azure Monitor Metric | Source |
|-----|---------------------|--------|
| Availability | Custom probe metric | `/readyz` HTTP status |
| Latency | `api.response_time_ms` | `src/infrastructure/monitoring/azure_monitor.py` |
| Error rate | `api.error_count`, `api.request_count` | Middleware counter |
| Auth success | `auth.login_success`, `auth.login_failure` | `src/api/routes/auth.py` |
| DLQ depth | `celery.dlq_depth` | `src/infrastructure/tasks/monitor_tasks.py` |
| Circuit breaker | `circuit_breaker.state_change` | `src/infrastructure/resilience/` |

---

## Error Budget Policy

1. **Budget remaining > 50%**: Normal development velocity; all changes follow standard process
2. **Budget remaining 20-50%**: Increased monitoring; new features require additional review; prioritize reliability work
3. **Budget remaining < 20%**: Feature freeze for non-reliability work; all engineering effort on stability and resilience
4. **Budget exhausted**: Mandatory incident review; post-mortem for every SLO breach; CTO notification

---

## Dashboard Requirements

Each SLO should have a dashboard panel showing:
- Current SLI value (real-time)
- SLO target line
- Error budget consumption (rolling 30 days)
- Trend (7-day moving average)
- Recent breaches (last 30 days)
