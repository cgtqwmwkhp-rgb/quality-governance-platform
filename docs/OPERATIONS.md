# Operations Runbook

## Health Check Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /healthz` | Liveness probe — confirms the process is running | `200 OK` with `{"status": "healthy"}` |
| `GET /readyz` | Readiness probe — confirms database and dependencies are reachable | `200 OK` when all checks pass; `503` otherwise |

**Monitoring**: The Docker `HEALTHCHECK` instruction calls `/healthz` every 15 seconds. Kubernetes or Azure Container Apps should target `/readyz` for readiness gates.

## Deployment Process

1. Push to `main` triggers the `deploy-production.yml` GitHub Actions workflow.
2. The workflow builds a Docker image tagged with the commit SHA.
3. The image is pushed to the Azure Container Registry.
4. Azure Container App is updated to the new image.
5. Post-deploy smoke tests verify health, CORS, and critical endpoints.
6. If smoke tests fail, the automated rollback job activates (see below).

## Rollback Procedure

### Automated Rollback

The CI/CD pipeline includes an automatic rollback job that fires when the `build-and-deploy` job fails. It:

1. Logs in to Azure.
2. Reverts the Container App to the previous image (`previous_image` output).
3. Waits 30 seconds and verifies `/healthz` returns `200`.

### Manual Rollback

```bash
# Identify the last known-good image tag
az containerapp revision list \
  --name <APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --output table

# Revert to a specific image
az containerapp update \
  --name <APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --image <REGISTRY>/<IMAGE>:<PREVIOUS_SHA>
```

## Monitoring and Alerting

| Signal | Tool | Threshold |
|--------|------|-----------|
| HTTP 5xx rate | Azure Monitor / Application Insights | > 1% over 5 min |
| Response latency (p95) | Application Insights | > 2 s |
| Container restarts | Azure Container Apps metrics | > 2 in 10 min |
| CPU / Memory utilisation | Azure Monitor | > 80% sustained |

Configure Azure Action Groups to route alerts to the on-call channel (email, Slack, or PagerDuty).

## Common Troubleshooting

### Application won't start

1. Check container logs: `az containerapp logs show --name <APP> --resource-group <RG> --follow`
2. Verify environment variables are set (especially `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`).
3. Ensure the database is reachable from the container's virtual network.

### `/readyz` returning 503

1. Check database connectivity — the readiness probe queries the database.
2. Verify the connection string and that the database server is running.
3. Look for connection-pool exhaustion in logs.

### High latency

1. Check cache hit rates: `GET /api/v1/cache/stats`.
2. Look for slow queries in Application Insights or database logs.
3. Verify Redis is reachable if `REDIS_URL` is configured.

### Authentication failures

1. Confirm `JWT_SECRET_KEY` matches across all replicas.
2. Check token expiry settings (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
3. For Azure AD, verify `AZURE_CLIENT_ID` and `AZURE_TENANT_ID`.

## Database Migration Process

Migrations are managed with **Alembic**.

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Show current migration state
alembic current
```

In production, migrations run automatically during deployment via the CI/CD pipeline. To run manually:

```bash
az containerapp exec --name <APP> --resource-group <RG> -- alembic upgrade head
```

## Cache Management

The platform uses Redis (with an in-memory fallback) for caching. Cache TTLs are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_SHORT` | 60 | Frequently changing data |
| `CACHE_TTL_MEDIUM` | 300 | Moderately stable data |
| `CACHE_TTL_LONG` | 3600 | Stable reference data |
| `CACHE_TTL_DAILY` | 86400 | Very stable data |
| `CACHE_TTL_SESSION` | 1800 | Session data |
| `CACHE_TTL_DEFAULT` | 300 | Default TTL when none specified |

### Admin Endpoints (superuser only)

| Action | Endpoint |
|--------|----------|
| View stats | `GET /api/v1/cache/stats` |
| Clear all | `POST /api/v1/cache/clear` |
| Invalidate pattern | `DELETE /api/v1/cache/{pattern}` |

### Redis connectivity issues

If Redis becomes unreachable, the cache layer automatically falls back to an in-memory LRU cache. Recovery is attempted via the `reconnect()` method, which can be triggered from a health check or manually.
