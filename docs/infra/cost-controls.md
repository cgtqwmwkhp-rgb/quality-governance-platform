# Quality Governance Platform — Cost Controls & FinOps

**Owner**: Platform Engineering
**Last Updated**: 2026-03-21
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

**Estimated Monthly Total**: ~£130–£140 (all environments)

> **Note**: Production-only cost is ~£80/month (see [`docs/evidence/capacity-profile.md`](../evidence/capacity-profile.md)).
> The higher range here includes staging, ACR, Redis, and Blob storage.

---

## 2. Cost Drivers & Optimisation Controls

### 2.1 Compute (App Service)

- **Current**: B1/B2 tier (1–2 vCPU, 1.75–3.5 GB RAM)
- **Control**: Auto-scale configured with min 2, max 6 instances (see `scripts/infra/autoscale-settings.json`). Scale-out triggers on CPU > 70% sustained 5 minutes; scale-in on CPU < 30% sustained 10 minutes.
- **Alert**: If CPU consistently >80% over 1 hour across all instances → evaluate scale-up to S1
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

## Unit Economics

| Metric | Estimated Value | Notes |
|--------|----------------|-------|
| Cost per tenant (monthly) | ~£15–25 | Shared infrastructure; scales sub-linearly with tenants |
| Cost per active user (monthly) | ~£2–5 | Based on ~£110–160 total / ~50–100 active users |
| Infrastructure cost per API request | ~£0.0001 | Compute + DB amortised across ~5,000 req/day baseline |

Unit economics will be refined as per-tenant cost attribution (§8) matures and Azure Cost Management custom dimensions are enabled.

---

## 3. Resource Tagging Policy

All Azure resources provisioned for the Quality Governance Platform **must** carry the following tags for cost allocation, ownership, and automation:

| Tag | Required values | Purpose |
|-----|-----------------|---------|
| `environment` | `prod`, `staging`, or `dev` | Scope spend and alerts by lifecycle stage |
| `service` | `qgp-api`, `qgp-frontend`, `qgp-db`, or `qgp-cache` | Map cost to application component |
| `cost-center` | `engineering` | Chargeback / showback alignment |
| `owner` | `platform-team` | Accountability and escalation |

**Enforcement**: Apply tags at creation time (ARM/Bicep, Terraform, or portal). Azure Policy may be used to deny or audit untagged creations. Existing resources should be backfilled during the next change window.

---

## 4. Budget Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Monthly spend exceeds £180 | 115% of estimated budget | Investigate spike; check for orphan resources |
| Database storage >80% | 25.6 GB of 32 GB | Extend storage or archive audit trail |
| Blob storage >10 GB | Absolute | Apply lifecycle policy |
| App Service CPU >80% sustained | 1 hour window | Evaluate scale-up |
| ACR storage >5 GB | Absolute | Run image purge |
| GitHub Actions >1500 min | 75% of limit | Add caching, reduce matrix |

**Implementation**: Azure Cost Management budget alerts (Azure Portal → Cost Management → Budgets), or deploy the subscription-scoped ARM template in `scripts/infra/budget-alert.json` (see **Monthly Budget Template** below).

---

## 5. Monthly Budget Template

Platform cloud spend is capped with an Azure Budget of **USD 500 per month**, with email notifications at **80%** (warning) and **100%** (critical).

The canonical ARM definition lives in **`scripts/infra/budget-alert.json`**. Deploy at **subscription** scope (example):

```bash
az deployment sub create \
  --location uksouth \
  --template-file scripts/infra/budget-alert.json
```

**Snippet** (core `Microsoft.Consumption/budgets` resource — full template with parameters in `scripts/infra/budget-alert.json`):

```json
{
  "type": "Microsoft.Consumption/budgets",
  "apiVersion": "2023-05-01",
  "name": "qgp-monthly-budget",
  "properties": {
    "category": "Cost",
    "amount": 500,
    "timeGrain": "Monthly",
    "timePeriod": {
      "startDate": "2026-03-01T00:00:00Z",
      "endDate": "2030-12-31T23:59:59Z"
    },
    "filter": {},
    "notifications": {
      "WarningActual80Percent": {
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 80,
        "thresholdType": "Actual",
        "contactEmails": ["platform-team@plantexpand.com"]
      },
      "CriticalActual100Percent": {
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 100,
        "thresholdType": "Actual",
        "contactEmails": [
          "platform-team@plantexpand.com",
          "engineering-lead@plantexpand.com"
        ]
      }
    }
  }
}
```

**Note**: Budget amounts are interpreted in the subscription’s **billing currency**. If billing is in GBP, confirm the equivalent cap in Cost Management or adjust `amount` to match the £ target.

---

## 6. Cost Optimization Checklist

Use this checklist in monthly reviews and before quarterly optimization work:

- [ ] **Reserved capacity for database** — Evaluate Azure Database for PostgreSQL flexible server reserved capacity where a 1-year commitment is acceptable; compare to burstable pay-as-you-go.
- [ ] **Right-sizing review (quarterly)** — App Service SKU, PostgreSQL compute/storage, Redis tier, and ACR: compare metrics (CPU, memory, connections, storage growth) to provisioned capacity.
- [ ] **Unused resource cleanup** — Remove or consolidate stopped apps, empty resource groups, orphaned disks/Public IPs, stale images in ACR, and dev sandboxes past TTL.
- [ ] **Dev / staging shutdown schedule** — Scale non-production environments down or off during **nights and weekends** (e.g. automation or manual runbook) unless explicit testing requires uptime; document exceptions.

---

## 7. FinOps Review Cadence

| Cadence | Activity |
|---------|----------|
| **Monthly** | **Cost review meeting** — Reconcile Azure Cost Management + this document’s inventory; review budget alerts, tagging compliance, and checklist items; assign follow-ups for anomalies. |
| **Quarterly** | **Optimization sprint** — Dedicated time for reserved-instance analysis, right-sizing changes, lifecycle policies (Blob), CI/cache efficiency, and closure of prior action items. |

This cadence complements the operational steps in **Cost Review Process** (section 9).

---

## 8. Per-Tenant Cost Attribution

### Current State

- **Partial** — all tenants share the same infrastructure (single-deployment, multi-tenant with `tenant_id` row-level isolation)
- Backend request logging includes `tenant_id` in structured logs (`src/infrastructure/middleware/request_logger.py`)
- Blob storage is tenant-scoped by key prefix (`evidence/{tenant_id}/...`)

### Implementation Plan

| Phase | Action | Status |
|-------|--------|--------|
| Phase 1 | Log `tenant_id` with every request for usage-based attribution | Done |
| Phase 2 | Tag Azure Blob containers per tenant for storage cost breakdown | Planned |
| Phase 3 | Azure Cost Management custom dimensions for per-tenant cost views | Planned |
| Phase 4 | Monthly per-tenant cost report generation and delivery | Planned |

### Target Model

- Tag resources with `tenant_id` where possible (Blob containers per tenant)
- Use Azure Cost Management tags and custom dimensions for attribution
- Generate monthly per-tenant cost reports from Azure Cost Management API
- Backend telemetry enrichment enables usage-proportional chargeback

---

## 9. Cost Review Process

1. **Monthly**: Review Azure Cost Management dashboard against budget
2. **Quarterly**: Evaluate reserved instance vs pay-as-you-go
3. **On scale event**: Before any SKU upgrade, document expected cost delta and approval
4. **On new resource**: Add to this inventory table with estimated monthly cost

---

## 10. Evidence Pointers

| Control | Evidence Location |
|---------|-------------------|
| DB pool config | `src/infrastructure/database.py` L42–54 |
| Statement timeout | `src/infrastructure/database.py` — `statement_timeout=30000` |
| Rate limiting | `src/infrastructure/middleware/rate_limiter.py` |
| Resource metrics endpoint | `src/api/routes/health.py` — `/api/v1/health/metrics/resources` |
| Bundle size limits | `frontend/.size-limit.json` — 350kB/250kB/50kB |
| CI performance budget | `.github/workflows/ci.yml` — `performance-budget` job |
| ACA provisioning | `scripts/infra/provision-aca-staging.sh` — MIN_REPLICAS=1, MAX_REPLICAS=3 |
| Azure monthly budget (ARM) | `scripts/infra/budget-alert.json` — `qgp-monthly-budget`, USD 500, 80%/100% notifications |
| Cost controls & FinOps (D26) | `docs/infra/cost-controls.md` — tagging policy, budget template, checklist, cadence |
