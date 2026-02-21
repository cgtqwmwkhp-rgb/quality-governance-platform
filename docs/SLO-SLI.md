# SLO/SLI Definitions — Quality Governance Platform

## Overview

**Service Level Objectives (SLOs)** are target reliability goals expressed as a percentage over a rolling time window. They define "good enough" reliability so the team can balance feature velocity against operational stability.

**Service Level Indicators (SLIs)** are the quantitative measurements that feed each SLO. Every SLI has a clearly defined measurement method, data source, alerting threshold, and error budget so that on-call engineers can act before users are impacted.

The error budget for each SLO is calculated as `1 − SLO target`. When the remaining error budget drops below 25 %, a change-freeze is recommended until the budget recovers.

---

## 1. API Availability

| Field | Value |
|---|---|
| **SLO** | 99.9 % of health-check probes return HTTP 200 over a 30-day rolling window |
| **SLI** | `successful_health_checks / total_health_checks × 100` |
| **Measurement method** | Synthetic HTTP GET to `/healthz` every 30 seconds from the Azure Front Door health probe |
| **Data source** | Azure Monitor availability tests; OpenTelemetry `api.health_check` metric |
| **Alerting threshold** | Page on-call when availability drops below 99.95 % over any 5-minute window |
| **Error budget** | 0.1 % → ~43 minutes of downtime per 30-day window |

---

## 2. API Latency

| Field | Value |
|---|---|
| **SLO** | P95 response time < 500 ms; P99 response time < 2 s over a 30-day rolling window |
| **SLI** | Histogram of request duration in milliseconds for all non-health-check endpoints |
| **Measurement method** | OpenTelemetry HTTP server span duration recorded by FastAPI instrumentation |
| **Data source** | `api.response_time_ms` histogram exported to Azure Monitor / Prometheus |
| **Alerting threshold** | Warn when P95 > 400 ms for 5 minutes; page when P95 > 500 ms or P99 > 2 s for 5 minutes |
| **Error budget** | Any 30-day period where P95 exceeds 500 ms for more than 43 cumulative minutes is a budget violation |

---

## 3. Error Rate

| Field | Value |
|---|---|
| **SLO** | < 0.1 % of responses are 5xx errors over a 30-day rolling window |
| **SLI** | `count(status >= 500) / count(all_responses) × 100` |
| **Measurement method** | OpenTelemetry `api.error_rate_5xx` counter compared against total request count |
| **Data source** | `api.error_rate_5xx` counter; FastAPI middleware response status codes in Azure Monitor |
| **Alerting threshold** | Warn at 0.05 % 5xx rate over 5 minutes; page at 0.1 % over 5 minutes |
| **Error budget** | 0.1 % → roughly 1 in every 1 000 requests may fail before the budget is exhausted |

---

## 4. Deployment Success

| Field | Value |
|---|---|
| **SLO** | > 95 % of production deployments complete without rollback over a 90-day rolling window |
| **SLI** | `successful_deploys / total_deploys × 100` (a deploy is "successful" if no rollback occurs within 30 minutes) |
| **Measurement method** | GitHub Actions workflow outcome combined with rollback event detection in the CD pipeline |
| **Data source** | GitHub Actions API (`workflow_run` events); deployment audit log in the platform database |
| **Alerting threshold** | Notify release-engineering channel when two consecutive deployments require rollback |
| **Error budget** | 5 % → for every 20 deploys, 1 rollback is within budget |

---

## 5. Background Task Reliability

| Field | Value |
|---|---|
| **SLO** | < 1 % Celery task failure rate over a 30-day rolling window |
| **SLI** | `failed_tasks / total_tasks × 100` |
| **Measurement method** | Celery `task_postrun` signal; tasks with state `FAILURE` or `REVOKED` are counted as failures |
| **Data source** | `celery.task_failures` counter; Celery Flower dashboard; Azure Monitor custom metrics |
| **Alerting threshold** | Warn at 0.5 % failure rate over 15 minutes; page at 1 % over 15 minutes |
| **Error budget** | 1 % → 1 in 100 tasks may fail before the budget is exhausted |

---

## 6. Cache Effectiveness

| Field | Value |
|---|---|
| **SLO** | > 80 % cache hit rate over a 30-day rolling window |
| **SLI** | `cache_hits / (cache_hits + cache_misses) × 100` |
| **Measurement method** | OpenTelemetry `cache.operations` up-down counter and `cache.miss_rate` counter tracked per Redis GET |
| **Data source** | `cache.operations` metric; Redis `INFO stats` (`keyspace_hits`, `keyspace_misses`); Azure Cache for Redis metrics |
| **Alerting threshold** | Warn when hit rate drops below 85 % over 15 minutes; page when below 80 % over 15 minutes |
| **Error budget** | 20 % miss budget — if more than 1 in 5 lookups misses cache, investigate key expiry or eviction policies |

---

## Error Budget Policy

| Remaining Budget | Action |
|---|---|
| > 50 % | Normal development velocity; deploy at will |
| 25 – 50 % | Increase review rigour; require post-deploy smoke tests |
| < 25 % | Change-freeze for non-critical changes; focus on reliability improvements |
| Exhausted (0 %) | Full change-freeze until budget recovers; incident review required for every new violation |

---

## Dashboard & Reporting

- **Real-time**: Azure Monitor workbook aggregating all six SLIs with burn-rate alerts.
- **Weekly**: Automated SLO compliance report posted to `#platform-reliability` Slack channel.
- **Monthly**: Error budget consumption review during the platform retrospective.
