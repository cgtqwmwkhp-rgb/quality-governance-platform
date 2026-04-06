# Capacity & Scalability Profile (D25 / D26)

**Owner**: Platform Engineering
**Last Updated**: 2026-04-04
**Environment**: Azure App Service B2 (production)

---

## Current Infrastructure

| Resource | Specification | Monthly Cost | Evidence |
|----------|---------------|--------------|----------|
| App Service Plan | B2 (2 vCPU, 3.5 GB RAM) | ~£50 | Azure portal |
| PostgreSQL Flexible | Burstable B1ms (1 vCPU, 2 GB) | ~£25 | Azure portal |
| Static Web App | Free tier | £0 | Azure portal |
| Azure Monitor | Basic (included) | ~£5 | Azure portal |
| **Total (production only)** | | **~£80/month** | Azure Cost Management |

> **Scope note**: This table covers **production infrastructure only**. The full platform cost
> including staging (£35), ACR (£4), Redis (£12), and Blob storage (£1-5) is **~£130-£140/month**.
> See [`docs/infra/cost-controls.md`](../../docs/infra/cost-controls.md) for the complete inventory.

## Cost Attribution

| Tag | Value | Purpose |
|-----|-------|---------|
| `project` | `qgp` | Cost centre allocation |
| `environment` | `production` / `staging` | Environment separation |
| `owner` | `platform-eng` | Accountability |
| `budget-alert` | `180-gbp` | Azure Cost Management alert threshold |

## Scaling Profile

### Current Capacity (B2 — Single Instance)

| Metric | Measured Value | Source |
|--------|---------------|--------|
| Sustained RPS | ~50 req/s | Locust CI gate (20 concurrent users) |
| Peak RPS (burst) | ~100 req/s | Locust CI artifacts |
| p95 latency at load | < 500 ms | CI `locust-load-test` gate |
| Concurrent users supported | 20+ | CI gate configuration |
| DB connections (pool) | 20 (configurable) | `src/core/config.py` pool settings |

### Scaling Path

| Trigger | Action | Target | Est. Capacity |
|---------|--------|--------|---------------|
| Sustained CPU > 70% for 15 min | Scale up to B3 | 4 vCPU, 7 GB RAM | ~150 req/s |
| Sustained CPU > 70% on B3 | Scale out (2 instances) | 2 × B3 | ~300 req/s |
| DB connection pool > 80% | Scale DB to GP B2ms | 2 vCPU, 4 GB | ~100 concurrent queries |
| Storage > 80% capacity | Extend DB storage | +10 GB | Transparent |

### Cost Projections

| Scenario | Infrastructure | Est. Monthly Cost |
|----------|---------------|-------------------|
| Current (< 50 users) | B2 + Burstable B1ms | ~£80 |
| Growth (50-200 users) | B3 + GP B2ms | ~£180 |
| Scale (200-500 users) | 2×B3 + GP B4ms | ~£350 |

## Budget Controls

| Control | Configuration | Evidence |
|---------|---------------|----------|
| Monthly budget alert (80%) | £144 threshold | `docs/observability/alerting-rules.md` |
| Monthly budget alert (100%) | £180 threshold | `docs/observability/alerting-rules.md` |
| Cost anomaly detection | Azure Cost Management | Azure portal |
| Resource tagging policy | `project=qgp` mandatory | Azure Policy |

## Load Test Validation

CI-enforced load testing runs on every push to `main` and every PR:

| Gate | Threshold | Enforcement | Evidence |
|------|-----------|-------------|----------|
| p95 response time | < 500 ms | Blocking CI gate | `.github/workflows/ci.yml` `locust-load-test` job |
| Error rate | < 1% | Blocking CI gate | `tests/performance/locustfile.py` |
| Detailed results | CSV artifacts | CI artifact upload | `locust-results/stats.csv` |

See [`docs/evidence/load-test-baseline.md`](load-test-baseline.md) for detailed per-endpoint targets and historical results.
