# OpenTelemetry & Azure Monitor Alert Proof

**Status**: Partial — code evidence complete; live alert screenshot requires SRE input (see below)  
**Date**: 2026-04-07  
**Assessed by**: World-Class Scorecard 2026-04-07 (EG-06 remediation)  
**Evidence classification**: BLOCKED BY ENVIRONMENT for live telemetry screenshots

---

## 1. Code-Level OTel Integration Evidence

### 1.1 Instrumentation module

**File**: `src/infrastructure/monitoring/azure_monitor.py`

- Module docstring confirms: `"OpenTelemetry instrumentation and Azure Monitor integration."`
- Imports (conditional, guarded by availability):
  - `opentelemetry.sdk.trace` — `TracerProvider`, `BatchSpanProcessor`
  - `opentelemetry.sdk.metrics` — `MeterProvider`, `PeriodicExportingMetricReader`
  - `opentelemetry.instrumentation.fastapi` — `FastAPIInstrumentor` (auto-instruments all routes)
  - `opentelemetry.sdk.trace.sampling` — `ParentBased`, `TraceIdRatioBased`
- Business metric counters and histograms defined at module level (lines 62–88)
- `initialize_telemetry()` function (line 89) wires `TracerProvider` + `MeterProvider` with Azure Monitor exporter

### 1.2 Structured logging with trace correlation

**Directory**: `src/infrastructure/logging/`

- `__init__.py` — logging configuration with OTel context propagation
- `context.py` — request context enrichment (correlation IDs attached to every log record)
- `trace_context.py` — extracts `trace_id` and `span_id` from active OTel span for log correlation
- `pii_filter.py` — PII scrubbing applied before log emission

### 1.3 FastAPI middleware integration

**File**: `src/infrastructure/middleware/request_logger.py`

- Logs every inbound request with correlation ID and duration
- Trace context injected at middleware layer, propagated to all downstream spans

---

## 2. Azure Monitor Alert Configuration

### 2.1 Infra definition

**File**: `docs/evidence/main.bicep`

- Azure Monitor alert rules expected here — SRE to confirm ARM/Bicep definitions for:
  - Error rate threshold (HTTP 5xx > X% over 5 min)
  - Readiness probe failure alert (per ADR-0014)
  - Response latency alert (P95 > 2s)

### 2.2 Kusto query reference (from ADR-0014)

```kusto
requests
| where name == "GET /readyz"
| where resultCode != "200"
| summarize count() by bin(timestamp, 5m), resultCode
```

---

## 3. Live Alert Proof — ACTION REQUIRED (SRE)

The following evidence cannot be captured autonomously from this environment. An SRE or platform operator must complete this section before the D13 score can reach 9.5.

| Required Evidence | Where to Capture | Owner |
|-------------------|------------------|-------|
| Screenshot of active Azure Monitor alert rules in `rg-qgp-staging` | Azure Portal → Monitor → Alerts | SRE |
| Screenshot of active Azure Monitor alert rules in `rg-qgp-prod` | Azure Portal → Monitor → Alerts | SRE |
| Sample Application Insights live trace showing `trace_id` correlation | Azure Portal → App Insights → Live Metrics | SRE |
| Sample alert firing + resolution event (last 30 days) | Azure Portal → Monitor → Alert history | SRE |

**Target file location for evidence**: `docs/evidence/otel-alert-proof-screenshots/` (create folder, add PNG exports named `azure-monitor-alerts-staging-YYYY-MM-DD.png` etc.)

---

## 4. Assessment Context

| Dimension | D13 — Observability |
|-----------|---------------------|
| Prior WCS (2026-04-03) | 7.2 |
| Current WCS (2026-04-07) | 7.2 (unchanged — live proof still missing) |
| Gap to 9.5 | 2.3 |
| Blocker for improvement | Live alert screenshot + confirmed alert policy in both environments |
