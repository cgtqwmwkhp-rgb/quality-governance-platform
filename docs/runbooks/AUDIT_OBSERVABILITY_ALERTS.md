# Audit Observability and Alerting

Version: 1.0  
Owner: Platform Engineering  
Scope: Audit templates, runs, responses, completion, findings

## Telemetry Event Contract

Audit endpoints emit structured log events with:

- `message`: `audit_endpoint_event`
- `endpoint`: bounded endpoint identifier
- `status_code`: HTTP status
- `duration_ms`: request execution time
- `error_class`: bounded error category (`none`, `template_not_published`, `run_not_found`, `run_not_writable`, `duplicate_response`, `invalid_status_transition`)

## Covered Endpoints

- `GET /api/v1/audits/templates`
- `POST /api/v1/audits/runs`
- `POST /api/v1/audits/runs/{id}/responses`
- `POST /api/v1/audits/runs/{id}/complete`
- `POST /api/v1/audits/runs/{id}/findings`

## Azure Log Analytics Queries

### Error Rate by Endpoint (5-minute bins)

```kusto
AppTraces
| where Message has "audit_endpoint_event"
| extend endpoint = tostring(Properties.endpoint)
| extend status_code = toint(Properties.status_code)
| summarize total=count(), errors=countif(status_code >= 400) by endpoint, bin(TimeGenerated, 5m)
| extend error_rate = todouble(errors) / iif(total == 0, 1.0, todouble(total))
| order by TimeGenerated desc
```

### P95 Latency by Endpoint

```kusto
AppTraces
| where Message has "audit_endpoint_event"
| extend endpoint = tostring(Properties.endpoint)
| extend duration_ms = todouble(Properties.duration_ms)
| summarize p95_latency_ms = percentile(duration_ms, 95), calls = count() by endpoint, bin(TimeGenerated, 15m)
| order by TimeGenerated desc
```

### Top Error Classes

```kusto
AppTraces
| where Message has "audit_endpoint_event"
| extend error_class = tostring(Properties.error_class)
| where error_class != "none"
| summarize count() by error_class, tostring(Properties.endpoint), bin(TimeGenerated, 15m)
| order by count_ desc
```

## Alert Definitions

### Critical: Audit Run Creation Failure Spike

- Condition: `POST /api/v1/audits/runs` `status_code >= 400` > 10 in 5 minutes
- Severity: Critical
- Action: page on-call, block production promotion

### Warning: Audit Completion Latency Regression

- Condition: p95 latency for `POST /api/v1/audits/runs/{id}/complete` > 2000ms for 15 minutes
- Severity: Warning
- Action: investigate DB/API performance

### Warning: Duplicate Response Anomaly

- Condition: `error_class == duplicate_response` > 20 in 15 minutes
- Severity: Warning
- Action: check client retries and idempotency handling

## Incident Response

1. Confirm error class and endpoint trend in Kusto.
2. Correlate with release SHA from `/api/v1/meta/version`.
3. Run `scripts/smoke/post_deploy_check.py` and `scripts/smoke/audit_lifecycle_e2e.py`.
4. If critical criteria met, execute rollback runbook.
