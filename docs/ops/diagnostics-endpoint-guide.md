# Diagnostics & Admin Endpoint Guide (D32)

Reference for all administrative and diagnostic endpoints in the Quality Governance Platform.

## Health & Readiness

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/healthz` | GET | Liveness probe — confirms the process is running | No |
| `/readyz` | GET | Readiness probe — confirms DB connectivity and dependency health | No |
| `/api/v1/health/metrics/resources` | GET | Resource utilization (CPU, memory, connections) | Yes (admin) |

## System Information

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/v1/health/build` | GET | Build SHA, timestamp, version info | No |
| `/api/v1/feature-flags` | GET | List all feature flags and their states | Yes (admin) |

## Data Diagnostics

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/v1/audits/runs` | GET | List audit runs with pagination | Yes |
| `/api/v1/audits/findings` | GET | List findings with graceful degradation | Yes |
| `/api/v1/external-audit-imports/jobs` | GET | List import jobs and their statuses | Yes |
| `/api/v1/risks` | GET | Enterprise risk register entries | Yes |
| `/api/v1/actions` | GET | CAPA actions list | Yes |

## Troubleshooting Workflows

### 1. Application Not Responding

```bash
# Check liveness
curl https://app-qgp-prod.azurewebsites.net/healthz

# Check readiness (includes DB)
curl https://app-qgp-prod.azurewebsites.net/readyz

# Check build version
curl https://app-qgp-prod.azurewebsites.net/api/v1/health/build
```

### 2. Database Connectivity Issues

```bash
# readyz will return 503 if DB is unreachable
curl -v https://app-qgp-prod.azurewebsites.net/readyz

# Check Azure portal for PostgreSQL metrics
# Azure Portal → PostgreSQL → Monitoring → Metrics → Active connections
```

### 3. Import Job Stuck

```bash
# List recent import jobs
curl -H "Authorization: Bearer $TOKEN" \
  https://app-qgp-prod.azurewebsites.net/api/v1/external-audit-imports/jobs

# Check specific job status
curl -H "Authorization: Bearer $TOKEN" \
  https://app-qgp-prod.azurewebsites.net/api/v1/external-audit-imports/jobs/123
```

### 4. Log Access

```bash
# Stream live logs from Azure
az webapp log tail --resource-group qgp-rg --name app-qgp-prod

# Query Kudu logs
az webapp log download --resource-group qgp-rg --name app-qgp-prod
```

## Related Documents

- [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) — on-call procedures
- [`docs/observability/correlation-guide.md`](../observability/correlation-guide.md) — request tracing
- [`src/api/routes/health.py`](../../src/api/routes/health.py) — health endpoints
