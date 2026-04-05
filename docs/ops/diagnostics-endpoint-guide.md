# Diagnostics & Admin Endpoint Guide (D32)

Reference for all administrative and diagnostic endpoints in the Quality Governance Platform.

## Health & Readiness

Paths below are on the **API host** (e.g. `https://app-qgp-prod.azurewebsites.net`), not under `/api/v1/...`. For frontend (SWA) URLs, use [`docs/evidence/environment_endpoints.json`](../evidence/environment_endpoints.json).

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/healthz` | GET | Liveness probe — confirms the process is running | No |
| `/readyz` | GET | Readiness probe — confirms DB connectivity and dependency health | No |
| `/api/v1/health/diagnostics` | GET | Runtime diagnostics: Python version, PID, uptime, migration head, feature-flag count, dependency snapshot | No |
| `/api/v1/health/metrics/resources` | GET | Resource utilization (CPU, memory, connections) | No |

**Redis in `/readyz`:** Implementation in `src/api/routes/health.py` — if `settings.redis_url` is empty, the JSON shows `redis: not_configured` while DB may still be `ok`. That reflects **missing App Setting `REDIS_URL`** (or equivalent), not necessarily a fault. Enable Redis when idempotency/Celery features require it (`pyproject.toml` / `.env.example` document `REDIS_URL`).

## System Information

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/v1/meta/version` | GET | Build SHA (`build_sha`), timestamp (`build_time`), app name, environment | No |
| `/api/v1/feature-flags` | GET | List all feature flags and their states | Yes (any authenticated user) |

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
curl https://app-qgp-prod.azurewebsites.net/api/v1/meta/version
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
