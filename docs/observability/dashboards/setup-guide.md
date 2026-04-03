# Application Insights & OTel Setup Guide

**Platform:** Quality Governance Platform (QGP)
**Last Updated:** 2026-04-03

This guide covers end-to-end setup of Azure Application Insights for QGP, including KQL alert rule definitions and Action Group configuration.

---

## 1. Prerequisites

- Azure subscription with Application Insights resource provisioned (UK South)
- `APPLICATIONINSIGHTS_CONNECTION_STRING` set in App Service configuration (sourced from Key Vault)
- OpenTelemetry SDK configured in `src/core/telemetry.py`
- Production telemetry enabled per [ADR-0008](../../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md)

---

## 2. Application Insights Configuration

### 2.1 Backend (FastAPI)

1. Install the OpenTelemetry Azure Monitor exporter:
   ```bash
   pip install azure-monitor-opentelemetry-exporter
   ```

2. Ensure `APPLICATIONINSIGHTS_CONNECTION_STRING` is set in the environment (Key Vault reference in App Service).

3. The telemetry initialisation in `src/core/telemetry.py` configures:
   - **TracerProvider** with Azure Monitor exporter
   - **MeterProvider** for custom metrics
   - **LoggerProvider** for structured log forwarding
   - Sampling rate controlled by `OTEL_TRACE_SAMPLE_RATE` (default 1.0)

### 2.2 Frontend (React)

1. The frontend telemetry service (`frontend/src/services/telemetry.ts`) sends events to `/api/v1/telemetry/events`.
2. Events are buffered in localStorage and flushed on visibility change.
3. No separate Application Insights JavaScript SDK is required — telemetry flows through the backend API.

---

## 3. KQL Alert Rule Definitions

Create these as **Scheduled Query Rules** in Azure Monitor (Portal → Monitor → Alerts → Alert rules → Create → Custom log search).

### 3.1 API Response Time — p95 > 200ms

```kql
requests
| where timestamp > ago(15m)
| summarize p95 = percentile(duration, 95) by bin(timestamp, 15m)
| where p95 > 200
```

- **Severity:** High (Sev 2)
- **Evaluation frequency:** 5 minutes
- **Window:** 15 minutes
- **Action:** Page on-call via Action Group `ag-qgp-oncall`

### 3.2 API Response Time — p99 > 500ms

```kql
requests
| where timestamp > ago(15m)
| summarize p99 = percentile(duration, 99) by bin(timestamp, 15m)
| where p99 > 500
```

- **Severity:** Critical (Sev 1)
- **Evaluation frequency:** 5 minutes
- **Window:** 15 minutes
- **Action:** Page on-call via Action Group `ag-qgp-oncall`

### 3.3 API Response Time — p50 > 100ms

```kql
requests
| where timestamp > ago(1h)
| summarize p50 = percentile(duration, 50) by bin(timestamp, 1h)
| where p50 > 100
```

- **Severity:** Warning (Sev 3)
- **Evaluation frequency:** 15 minutes
- **Window:** 1 hour
- **Action:** Create ticket via Action Group `ag-qgp-tickets`

### 3.4 Database Query Time — Indexed p95 > 50ms

```kql
dependencies
| where type == "SQL"
| where timestamp > ago(15m)
| summarize p95 = percentile(duration, 95) by bin(timestamp, 15m)
| where p95 > 50
```

- **Severity:** Warning (Sev 3)
- **Evaluation frequency:** 5 minutes
- **Window:** 15 minutes
- **Action:** Investigate via Action Group `ag-qgp-tickets`

### 3.5 Database Query Time — Complex p99 > 200ms

```kql
dependencies
| where type == "SQL"
| where timestamp > ago(15m)
| summarize p99 = percentile(duration, 99) by bin(timestamp, 15m)
| where p99 > 200
```

- **Severity:** Warning (Sev 3)
- **Evaluation frequency:** 5 minutes
- **Window:** 15 minutes
- **Action:** Investigate via Action Group `ag-qgp-tickets`

### 3.6 Error Rate > 1%

```kql
requests
| where timestamp > ago(5m)
| summarize total = count(), failed = countif(success == false) by bin(timestamp, 5m)
| extend error_pct = 100.0 * failed / total
| where error_pct > 1
```

- **Severity:** High (Sev 2)
- **Evaluation frequency:** 5 minutes
- **Window:** 5 minutes
- **Action:** Page on-call via Action Group `ag-qgp-oncall`

### 3.7 Throughput Drop (Business Hours)

```kql
requests
| where timestamp > ago(10m)
| summarize req_count = count() by bin(timestamp, 10m)
| where req_count < 6000 and hourofday(timestamp) between (8 .. 18)
```

- **Severity:** Warning (Sev 3)
- **Evaluation frequency:** 10 minutes
- **Window:** 10 minutes
- **Action:** Investigate via Action Group `ag-qgp-tickets`

---

## 4. Action Group Configuration

Create two Action Groups in Azure Monitor (Portal → Monitor → Alerts → Action groups):

### 4.1 `ag-qgp-oncall` (Critical / High alerts)

| Action type | Target | Purpose |
|-------------|--------|---------|
| Email | `platform-team@plantexpand.com` | Primary notification |
| Email | `engineering-lead@plantexpand.com` | Escalation |
| Webhook (future) | PagerDuty integration URL | Automated paging |

### 4.2 `ag-qgp-tickets` (Warning alerts)

| Action type | Target | Purpose |
|-------------|--------|---------|
| Email | `platform-team@plantexpand.com` | Awareness |
| Webhook (future) | Ticketing system API | Auto-create investigation ticket |

### 4.3 Setup Steps

1. Navigate to **Azure Portal → Monitor → Alerts → Action groups → Create**
2. Set **Resource group** to the QGP production resource group
3. Set **Region** to Global
4. Add notification targets per tables above
5. Tag with `service: qgp-api`, `environment: prod`

---

## 5. Dashboard Setup

### 5.1 Create Application Insights Dashboard

1. Navigate to **Azure Portal → Application Insights → [QGP resource] → Overview**
2. Pin key charts: Server response time, Server requests, Failed requests
3. Create a **shared dashboard** named `QGP Production Health`
4. Add custom KQL tiles for each alert rule (use queries from §3)

### 5.2 Recommended Dashboard Tiles

| Tile | KQL source | Visualisation |
|------|-----------|---------------|
| API p95 trend (24h) | §3.1 query with `ago(24h)` | Time chart |
| Error rate trend (24h) | §3.6 query with `ago(24h)` | Time chart |
| Throughput (requests/min) | `requests \| summarize count() by bin(timestamp, 1m)` | Time chart |
| Top 10 slowest endpoints | `requests \| summarize avg(duration) by name \| top 10 by avg_duration` | Bar chart |
| Dependency health | `dependencies \| summarize successRate=100.0*countif(success)/count() by type` | Pie chart |
| Active users (1h) | `customEvents \| where timestamp > ago(1h) \| summarize dcount(user_Id)` | Scalar |
| Failed requests by endpoint | `requests \| where success == false \| summarize count() by name \| top 10 by count_` | Table |

---

## 6. Verification Checklist

- [ ] `APPLICATIONINSIGHTS_CONNECTION_STRING` is set and resolves in App Service
- [ ] Backend traces appear in Application Insights → Transaction search within 5 minutes of deployment
- [ ] Frontend telemetry events appear in `customEvents` table
- [ ] All 7 scheduled query rules are created and enabled
- [ ] Action Groups fire test notifications successfully
- [ ] Dashboard tiles render with live data

---

## Related Documents

- [`docs/observability/alerting-rules.md`](../alerting-rules.md) — alert rule summary table
- [`docs/observability/telemetry-enablement-plan.md`](../telemetry-enablement-plan.md) — enablement plan
- [`docs/ops/kql-queries.md`](../../ops/kql-queries.md) — operational KQL query library
- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine ADR
