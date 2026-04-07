# OpenTelemetry Distributed Tracing — Evidence (D13)

**Platform:** Quality Governance Platform (QGP)
**Evidence Date:** 2026-04-07
**Dimension:** D13 Observability

---

## Configuration Summary

| Component | Detail | Source |
|-----------|--------|--------|
| OTel SDK | `opentelemetry-api==1.40.0`, `opentelemetry-sdk` | `requirements.lock` |
| Instrumentation | `opentelemetry-instrumentation-fastapi` (auto-instruments all routes) | `requirements.txt` |
| Trace exporter | `AzureMonitorTraceExporter` → Application Insights | `src/infrastructure/monitoring/azure_monitor.py` lines 125–128 |
| Span processor | `BatchSpanProcessor` (non-blocking, efficient) | `azure_monitor.py` line 128 |
| Sample rate | Production: 10% (`TraceIdRatioBased(0.1)`); non-prod: 100% | `azure_monitor.py` line 109–113 |
| Trace resource | `service.name=quality-governance-platform`, `service.version`, `deployment.environment` | `azure_monitor.py` lines 101–107 |
| Tracer provider | `TracerProvider` with `ParentBased` sampler | `azure_monitor.py` line 115 |

## Instrumented Code Paths

| Route / Service | Instrumentation Method | Evidence Path |
|----------------|------------------------|---------------|
| All FastAPI routes | `FastAPIInstrumentor` (auto) | `src/infrastructure/monitoring/azure_monitor.py` `setup_telemetry(app=app)` |
| CAPA route spans | Manual `get_tracer()` call | `src/api/routes/capa.py` line 19 |
| Compliance analysis | `get_tracer()` context spans on `/analyze` | `src/api/routes/compliance.py` |
| Audit operations | Automatic span capture via FastAPI instrumentation | All audit route handlers |

## Trace Correlation

- **Correlation IDs:** `docs/observability/correlation-guide.md`
- **Alert proof:** `docs/evidence/otel-alert-proof-2026-04-07.md` (live alert round-trip verification 2026-04-07)
- **Connection string:** Configured via `APPLICATIONINSIGHTS_CONNECTION_STRING` Azure App Setting (staging + production verified in `docs/evidence/env-parity-verification.md`)

## Application Insights Trace Configuration

```
Endpoint: Azure Application Insights (UK South region)
Connection string: Injected at runtime — see Azure Key Vault / App Settings
Telemetry table: traces, dependencies, requests (auto-correlated)
Retention: 90 days
```

## Verification Steps

To verify live traces are flowing:

```bash
# 1. Make an authenticated API call to staging/production
curl -H "Authorization: Bearer $TOKEN" https://$APP_URL/api/v1/incidents/ -s -o /dev/null -w "%{http_code}"

# 2. Navigate to Azure Portal → Application Insights → Transaction Search
#    Filter: time range = last 5 min, operation name = "GET /api/v1/incidents/"
#    Expected: correlated request + dependency spans visible

# 3. Verify sampling
curl $APP_URL/api/v1/meta/version | jq .build_sha
# Confirm build_sha matches the HEAD commit of the deployment
```

## Compliance Notes

- FastAPI instrumentation auto-captures HTTP method, URL, status code, duration on every request span.
- `BatchSpanProcessor` ensures traces do not block request handling (fire-and-forget to AI export endpoint).
- `ParentBased` sampler ensures parent-initiated traces are always completed (no orphaned child spans).
- In production, 10% sampling limits cost while maintaining statistical representativeness for SLO measurement.

---

**Status:** ACTIVE — traces exporting to Azure Monitor in staging and production.
