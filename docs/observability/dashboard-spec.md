# Telemetry Dashboard Specification (D28)

**Owner**: Platform Engineering
**Last Updated**: 2026-04-04
**Source Instruments**: `src/infrastructure/monitoring/azure_monitor.py`

---

## Dashboard: QGP Operations Overview

**Platform**: Azure Monitor Workbooks / Grafana
**Refresh**: 30 seconds

### Panel 1 — API Health

| Metric | Source Instrument | Visualisation | Alert Threshold |
|--------|-------------------|---------------|-----------------|
| Request rate (req/s) | OTel `http.server.request.duration` | Time series | < 10 req/s (business hours) |
| p50 / p95 / p99 latency | OTel `api.response_time_ms` | Percentile heatmap | p95 > 200 ms, p99 > 500 ms |
| Error rate (%) | OTel `http.server.response.status_code` 5xx | Gauge + sparkline | > 1% sustained 5 min |
| 5xx count | `record_5xx_error` → `_error_rate_5xx` counter | Bar chart | Any 5xx |

### Panel 2 — Authentication & Access

| Metric | Source Instrument | Visualisation | Alert Threshold |
|--------|-------------------|---------------|-----------------|
| Login count | `record_auth_login` → `_auth_login` counter | Time series | N/A (baseline) |
| Logout count | `record_auth_logout` → `_auth_logout` counter | Time series | N/A |
| Auth failures | `record_auth_failure` → `_auth_failures` counter | Bar chart (red) | > 10/min |
| Failure rate (%) | Derived: failures / (logins + failures) | Gauge | > 5% |

### Panel 3 — Domain Operations

| Metric | Source Instrument | Visualisation | Alert Threshold |
|--------|-------------------|---------------|-----------------|
| Incidents created | `record_incident_created` → `_incidents_created` | Counter + sparkline | N/A |
| Incidents resolved | `record_incident_resolved` → `_incidents_resolved` | Counter + sparkline | N/A |
| Audits completed | `record_audit_completed` → `_audits_completed` | Counter | N/A |
| Risks created | `record_risk_created` → `_risks_created` | Counter | N/A |
| Documents uploaded | `record_document_uploaded` → `_documents_uploaded` | Counter | N/A |
| Workflows completed | `record_workflow_completed` → `_workflows_completed` | Counter + duration histogram | Duration p95 > 24h |

### Panel 4 — Infrastructure

| Metric | Source Instrument | Visualisation | Alert Threshold |
|--------|-------------------|---------------|-----------------|
| DB query time | OTel `db.query_time_ms` | Percentile heatmap | p95 > 50 ms (indexed), p99 > 200 ms (complex) |
| DB pool utilisation | Application structured logs | Gauge | > 80% |
| Cache miss rate | `record_cache_miss` → `_cache_miss_rate` | Gauge | > 50% sustained |
| Celery task failures | `record_celery_task_failure` → `_celery_task_failures` | Counter (red) | Any failure |
| Circuit breaker state | `circuit_breaker.state` | Status indicator | OPEN |

### Panel 5 — SLO Burn Rate

| SLO | Target | Visualisation | Alert |
|-----|--------|---------------|-------|
| API availability | 99.9% (30-day) | Burn rate chart | > 2x burn for 1h |
| API latency p95 | < 200 ms | Compliance gauge | < 99% compliant |
| Error budget remaining | 43.2 min/month | Countdown | < 25% remaining |

---

## Instrument Coverage Matrix

| OTel Instrument | Dashboard Panel | Alert Rule | Status |
|----------------|-----------------|------------|--------|
| `api.response_time_ms` | 1 — API Health | p95/p99 alerts | Active |
| `db.query_time_ms` | 4 — Infrastructure | p95/p99 alerts | Active |
| `_incidents_created` counter | 3 — Domain Ops | — | Active |
| `_incidents_resolved` counter | 3 — Domain Ops | — | Active |
| `_audits_completed` counter | 3 — Domain Ops | — | Active |
| `_risks_created` counter | 3 — Domain Ops | — | Active |
| `_auth_login` counter | 2 — Auth | — | Active |
| `_auth_logout` counter | 2 — Auth | — | Active |
| `_auth_failures` counter | 2 — Auth | > 10/min | Active |
| `_documents_uploaded` counter | 3 — Domain Ops | — | Active |
| `_workflows_completed` counter | 3 — Domain Ops | Duration p95 | Active |
| `_error_rate_5xx` counter | 1 — API Health | Any 5xx | Active |
| `_cache_miss_rate` counter | 4 — Infrastructure | > 50% | Active |
| `_celery_task_failures` counter | 4 — Infrastructure | Any failure | Active |
