# Analytics and telemetry (D28)

Catalog of business metrics, frontend telemetry, backend observability signals, dashboards, pipeline, and privacy expectations for the Quality Governance Platform.

## Business event catalog (`track_metric` / `track_business_event`)

### Verified call sites (code references)

| API | Location | Call |
|-----|----------|------|
| `track_metric` | `src/domain/services/capa_service.py` | `"capa.created"` on create; `"capa.closed"` when status becomes closed |
| `track_metric` | `src/domain/services/complaint_service.py` | `"complaints.created"` on create |
| `track_metric` | `src/domain/services/audit_service.py` | `"audits.completed"` when a run completes; `"audits.findings"` when a finding is created |
| `track_business_event` | `src/domain/services/incident_service.py` | `"incident_created"` after incident create |
| `track_business_event` | `src/domain/services/audit_service.py` (`record_audit_event`) | `"audit_completed"` for each persisted audit trail event |

| `record_incident_created` | `src/domain/services/incident_service.py` | Direct counter increment on incident creation |
| `record_incident_resolved` | `src/domain/services/incident_service.py` | Counter increment when status transitions to CLOSED |
| `record_risk_created` | `src/domain/services/risk_service.py` | Counter increment after risk creation and DB commit |
| `record_document_uploaded` | `src/domain/services/evidence_service.py` | Counter increment after evidence asset upload and DB commit |
| `record_workflow_completed` | `src/domain/services/workflow_service.py` | Counter + duration histogram in `_complete_workflow()` |
| `record_auth_login` | `src/domain/services/auth_service.py` | Counter on successful authentication |
| `record_auth_failure` | `src/domain/services/auth_service.py` | Counter on failed authentication |
| `record_5xx_error` | `src/api/middleware/error_handler.py` | Counter in global error handler |
| `emit_db_pool_usage_metric` | `src/infrastructure/database.py` | Pool usage gauge via periodic task |

All core business metrics are now wired with direct call-sites. Remaining instruments (`auth.logout`, `celery.*`) are defined and ready for wiring when those code paths are enabled.

### `track_metric(name, value=1.0, tags=None)`

Registers a point on a **named counter** when the string matches a predefined instrument in [`src/infrastructure/monitoring/azure_monitor.py`](../../src/infrastructure/monitoring/azure_monitor.py). Unknown names create a **dynamic** counter on first use (use sparingly).

| Event / metric name | When fired (observed or intended) | Dimensions / tags | Visible on dashboard |
|---------------------|-----------------------------------|-------------------|----------------------|
| `incidents.created` | Counter reserved for incident creation | Optional OpenTelemetry attributes on `track_metric` | **Business Metrics** (see alerting doc) |
| `incidents.resolved` | Counter reserved for incident resolution | Optional attributes | **Business Metrics** |
| `audits.completed` | When an audit run is completed (`AuditService`) | Histogram of rates derived in backend | **Business Metrics** |
| `audits.findings` | When an audit finding is created | Optional attributes | **Business Metrics** |
| `capa.created` | On CAPA create (`CAPAService`) | — | **Business Metrics** |
| `capa.closed` | When CAPA transitions to closed (`CAPAService`) | — | **Business Metrics** |
| `complaints.created` | On complaint create (`ComplaintService`) | — | **Business Metrics** |
| `risks.created` | Wired via `record_risk_created()` in `RiskService.create_risk()` | — | **Business Metrics** |
| `auth.login` | Wired via `record_auth_login()` on successful `AuthService.authenticate()` | — | **Security** / **Business Metrics** |
| `auth.logout` | Instrument defined; wire at logout when enabled | — | **Security** |
| `auth.failures` | Wired via `record_auth_failure()` on failed `AuthService.authenticate()` | — | **Security** |
| `documents.uploaded` | Wired via `record_document_uploaded()` in `EvidenceService.upload()` | — | **Business Metrics** |
| `workflows.completed` | Wired via `record_workflow_completed()` in `WorkflowService._complete_workflow()` | duration_hours | **Business Metrics** |
| `api.error_rate_5xx` | Wired via `record_5xx_error()` in global error handler | — | **Platform Health** / **API Performance** |
| `cache.miss_rate` | Wired via `record_cache_miss()` (azure_monitor) | — | **Platform Health** |
| `db.pool_usage_percent` | Wired via `emit_db_pool_usage_metric()` (database.py) | — | **Platform Health** |
| `celery.task_failures` | On task failure when instrumented | — | **Platform Health** |
| `celery.queue_depth` | Queue depth gauge when instrumented | — | **Platform Health** |

### `track_business_event(event_name, properties=None)`

Emits **`track_metric(f"business.{event_name}", 1)`**. Because `business.*` is not in the static map, OpenTelemetry creates a **dynamic counter** per distinct `event_name` (first call), then increments it.

| Event name | When fired | Properties (logged) | Visible on dashboard |
|------------|------------|----------------------|----------------------|
| `incident_created` | After incident persistence (`IncidentService`) | `severity` | **Business Metrics** (incident rates) |
| `audit_completed` | On **every** `record_audit_event` helper invocation (broad audit trail hook) | `event_type`, `entity_type` | **Business Metrics** / log queries |

> **Note:** `audit_completed` is attached to the generic audit-event helper; interpret metrics as “audit trail event recorded,” not strictly “audit run completed,” unless you filter by `event_type` in log analytics.

### Related helpers (not `track_metric`)

| Helper | Signal | When used | Dashboard |
|--------|--------|-----------|-----------|
| `track_response_time(endpoint, duration_ms)` | Histogram `api.response_time_ms` | Per-request timing when instrumented from middleware or handlers | **API Performance** |
| `track_query_time(query, duration_ms)` | Histogram `db.query_time_ms` | Around DB calls when wrapped | **API Performance** / **Platform Health** |
| `track_cache_operation(hit: bool)` | UpDown `cache.operations` with attribute `result=hit|miss` | Cache wrapper | **Platform Health** |

Additional histogram: `workflow.completion_time_hours` (defined in telemetry setup; wire when workflows report duration).

## Frontend analytics

### Web Vitals

- **Entry (`main.tsx`)**: [`frontend/src/lib/webVitals.ts`](../../frontend/src/lib/webVitals.ts) loads `web-vitals` and reports **CLS**, **FID**, **LCP**, **TTFB**, and **INP** to `VITE_TELEMETRY_ENDPOINT` or `${API_BASE_URL}/api/v1/telemetry/web-vitals` via `sendBeacon` / `fetch`.
- **Hook (`App.tsx`)**: [`frontend/src/hooks/useWebVitals.ts`](../../frontend/src/hooks/useWebVitals.ts) also subscribes to **FCP**, **LCP**, **CLS**, **FID**, **TTFB**, and **INP** for development logging and optional `__VITALS_ENDPOINT__` beacons.

**Dashboard**: **API Performance** (latency and client-experience correlation) and browser-facing views in Application Insights when the connection string is configured.

### Page views

Route changes are not centrally named as “page_view” events in a single helper; primary client signals are **Web Vitals**, **error tracking** ([`frontend/src/services/errorTracker.ts`](../../frontend/src/services/errorTracker.ts)), and **experiment/login telemetry** (below). Add a small router listener if you need explicit `page_view` events in Application Insights.

### Experiment and login telemetry (allowlisted)

[`src/api/routes/telemetry.py`](../../src/api/routes/telemetry.py) accepts POST `/api/v1/telemetry/events` with **allowlisted** `name` and `dimensions` (no free-text PII). Examples include `exp001_form_opened`, `exp001_form_submitted`, `login_completed`, `login_error_shown`, etc.

**Dashboard**: **Business Metrics** and custom Log Analytics queries over `TELEMETRY_EVENT` structured logs.

## Backend metrics

- **HTTP**: OpenTelemetry FastAPI instrumentation (when OTel packages are installed) plus `api.response_time_ms` when `track_response_time` is used.
- **Database**: SQLAlchemy instrumentation (optional) and `db.query_time_ms` histogram.
- **Cache**: `cache.operations` up-down counter via `track_cache_operation`.
- **Celery**: `celery.task_failures`, `celery.queue_depth` when wired from workers.
- **Business counters**: See tables above.

## Custom dashboards

Panel definitions and alert contracts are documented in [`docs/observability/alerting-rules.md`](../observability/alerting-rules.md), including **Platform Health**, **API Performance**, **Business Metrics**, and **Security** sections.

## Data pipeline

1. **Instrumentation**: OpenTelemetry traces and metrics in-process (`setup_telemetry` in [`azure_monitor.py`](../../src/infrastructure/monitoring/azure_monitor.py)); structured JSON logs from request middleware.
2. **Export**: Azure Monitor exporters when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set.
3. **Consumption**: **Azure Monitor** → **Application Insights** (metrics, traces, logs) for dashboards and KQL queries.

Frontend Web Vitals POST to `/api/v1/telemetry/web-vitals` is logged as `WEB_VITALS` for correlation with server-side traces.

## Privacy compliance

- **No PII in telemetry payloads**: Experiment/login endpoints reject non-allowlisted dimensions; session IDs must remain anonymous (see module docstring in `telemetry.py`).
- **IP anonymization**: Configure truncation at the ingress / Application Insights collection layer per organizational policy (Azure supports IP masking settings).
- **Data retention**: Align Log Analytics workspace retention with GDPR / corporate policy; separate environments (dev/staging/prod) to limit accidental production data in lower environments.
- **Error payloads**: Client error beacons should avoid user-entered text; scrub or hash identifiers before extending schemas.
