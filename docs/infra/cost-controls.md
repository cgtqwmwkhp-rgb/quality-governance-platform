# Quality Governance Platform — Cost Controls & FinOps

**Owner**: Platform Engineering
**Last Updated**: 2026-03-20
**Review Cycle**: Monthly (with Azure billing cycle)

---

## 1. Infrastructure Inventory

| Resource | SKU / Tier | Region | Purpose | Monthly Est. |
|----------|-----------|--------|---------|-------------|
| Azure App Service (Production) | B1/B2 Linux | UK South | FastAPI backend + Gunicorn | ~£35–£65 |
| Azure App Service (Staging) | B1 Linux | UK South | Pre-prod validation | ~£35 |
| Azure Container Registry | Basic | UK South | Docker image storage | ~£4 |
| Azure Database for PostgreSQL Flexible | Burstable B1ms | UK South | Primary data store | ~£25–£40 |
| Azure Blob Storage | Hot / LRS | UK South | Evidence assets, photos | ~£1–£5 |
| Azure Key Vault | Standard | UK South | Secrets management | ~£0.03/10k ops |
| Azure Static Web Apps | Free | Global | React frontend (SWA) | £0 |
| Redis (App Service built-in or external) | Basic C0 | UK South | Rate limiting, idempotency, Celery broker | ~£12 |
| PAMS MySQL (External) | Existing | Azure | Fleet/vehicle data (read-only) | N/A (shared) |
| GitHub Actions | Free tier (2000 min/mo) | — | CI/CD pipeline | £0 |

**Estimated Monthly Total**: ~£110–£160

---

## 2. Cost Drivers & Optimisation Controls

### 2.1 Compute (App Service)

- **Current**: B1/B2 tier (1–2 vCPU, 1.75–3.5 GB RAM)
- **Control**: No auto-scale beyond single instance in production (sufficient for <100 concurrent users)
- **Alert**: If CPU consistently >80% over 1 hour → evaluate scale-up to S1
- **Savings opportunity**: Consider reserved instance pricing if commitment >1 year

### 2.2 Database (PostgreSQL Flexible)

- **Current**: Burstable B1ms (1 vCPU, 2 GB RAM, 32 GB storage)
- **Control**: `statement_timeout=30000` prevents runaway queries (`src/infrastructure/database.py`)
- **Control**: Connection pool capped at `pool_size=10, max_overflow=20` to prevent connection exhaustion
- **Alert**: Storage >80% → extend or archive old audit trail entries
- **Savings opportunity**: Burstable tier credits reduce cost during off-peak

### 2.3 Storage (Blob)

- **Current**: Hot tier, LRS redundancy
- **Control**: Evidence assets are tenant-scoped; no public CDN
- **Alert**: If storage >10 GB → review retention policy, move old evidence to Cool tier
- **Lifecycle policy**: Consider auto-tiering rule (Hot → Cool after 90 days, Cool → Archive after 365 days)

### 2.4 Container Registry

- **Current**: Basic tier
- **Control**: Only release-tagged images retained; CI images are ephemeral
- **Retention policy**: Purge untagged manifests older than 30 days (`az acr run --cmd "acr purge"`)

### 2.5 GitHub Actions

- **Current**: Free tier (2000 min/month for private repos)
- **Control**: 25+ CI jobs run in parallel; typical pipeline ~8 minutes
- **Alert**: If approaching 1500 min/month → optimise job matrix or add caching

---

## 3. Budget Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Monthly spend exceeds £180 | 115% of estimated budget | Investigate spike; check for orphan resources |
| Database storage >80% | 25.6 GB of 32 GB | Extend storage or archive audit trail |
| Blob storage >10 GB | Absolute | Apply lifecycle policy |
| App Service CPU >80% sustained | 1 hour window | Evaluate scale-up |
| ACR storage >5 GB | Absolute | Run image purge |
| GitHub Actions >1500 min | 75% of limit | Add caching, reduce matrix |

**Implementation**: Azure Cost Management budget alerts (set via Azure Portal → Cost Management → Budgets).

---

## 4. Per-Tenant Cost Attribution

### Current State

- **Not implemented** — all tenants share the same infrastructure
- The platform is single-deployment, multi-tenant (tenant isolation is at the DB row level via `tenant_id`)

### Target Model (when needed)

- Tag resources with `tenant_id` where possible (Blob containers per tenant)
- Use Azure Cost Management tags for attribution
- Backend: log `tenant_id` with request telemetry (`src/infrastructure/middleware/request_logger.py`) for usage-based attribution

---

## 5. Cost Review Process

1. **Monthly**: Review Azure Cost Management dashboard against budget
2. **Quarterly**: Evaluate reserved instance vs pay-as-you-go
3. **On scale event**: Before any SKU upgrade, document expected cost delta and approval
4. **On new resource**: Add to this inventory table with estimated monthly cost

---

## 6. Evidence Pointers

| Control | Evidence Location |
|---------|-------------------|
| DB pool config | `src/infrastructure/database.py` L42–54 |
| Statement timeout | `src/infrastructure/database.py` — `statement_timeout=30000` |
| Rate limiting | `src/infrastructure/middleware/rate_limiter.py` |
| Resource metrics endpoint | `src/api/routes/health.py` — `/api/v1/health/metrics/resources` |
| Bundle size limits | `frontend/.size-limit.json` — 350kB/250kB/50kB |
| CI performance budget | `.github/workflows/ci.yml` — `performance-budget` job |
| ACA provisioning | `scripts/infra/provision-aca-staging.sh` — MIN_REPLICAS=1, MAX_REPLICAS=3 |
