# Cost & Capacity Runbook

**Quality Governance Platform (QGP)**  
**Version:** 1.0  
**Last Updated:** 2026-03-03  
**Reference:** PR-07 Cost Efficiency (D26)

---

## 1. Monthly Cost Review Checklist

Complete this checklist within the first 5 business days of each month.

### 1.1 Cost Analysis

| Task | Owner | Status |
|------|-------|--------|
| [ ] Open Azure Cost Management → Cost analysis | | |
| [ ] Compare actual spend vs. budget for prior month | | |
| [ ] Identify top 5 cost drivers (by resource/service) | | |
| [ ] Check for unexpected spikes or new resources | | |
| [ ] Review cost by resource group and environment | | |
| [ ] Document variance and root cause (if > 10% over budget) | | |

### 1.2 Budget & Alerts

| Task | Owner | Status |
|------|-------|--------|
| [ ] Confirm budget alerts fired correctly (50%, 80%, 100%) | | |
| [ ] Verify alert recipients received notifications | | |
| [ ] Update budget amount if needed for next quarter | | |
| [ ] Run `scripts/infra/azure_cost_alert.sh --dry-run` to validate config | | |

### 1.3 Right-Sizing Review

| Task | Owner | Status |
|------|-------|--------|
| [ ] Review Azure Advisor cost recommendations | | |
| [ ] Check Container App CPU/memory utilization (see §2) | | |
| [ ] Review database DTU/vCore utilization | | |
| [ ] Identify idle or underutilized resources | | |
| [ ] Update capacity planning worksheet (§5) | | |

### 1.4 Documentation

| Task | Owner | Status |
|------|-------|--------|
| [ ] Update cost trend in capacity worksheet | | |
| [ ] Log any budget exceptions or approvals | | |
| [ ] Share summary with stakeholders (if applicable) | | |

---

## 2. Resource Right-Sizing Guidance

### 2.1 When to Right-Size Down

| Signal | Action |
|--------|--------|
| CPU utilization < 30% sustained for 7+ days | Reduce CPU allocation or replica count |
| Memory utilization < 50% sustained for 7+ days | Reduce memory allocation |
| Database DTU < 30% avg | Consider lower tier |
| Redis memory < 40% | Consider smaller tier |
| Zero traffic during off-hours | Enable scale-to-zero or reduce min replicas |

### 2.2 When to Right-Size Up

| Signal | Action |
|--------|--------|
| CPU > 80% sustained 5+ min | Increase CPU or add replicas (see SCALING_PLAYBOOK.md) |
| Memory > 85% sustained 5+ min | Increase memory allocation |
| Database DTU > 80% | Upgrade tier or optimize queries |
| Connection pool exhaustion | Increase pool size or database max_connections |

### 2.3 Docker Compose Resource Limits (Reference)

| Service | CPU Limit | Memory Limit | Memory Reservation |
|---------|-----------|--------------|---------------------|
| App | 1.0 | 512m | 256m |
| Postgres | 1.0 | 1g | 512m |
| Redis | 0.5 | 256m | 128m |

See `docker-compose.yml` and `docker-compose.sandbox.yml` for deploy.resources configuration.

### 2.4 Azure Container Apps Tiers

| Tier | CPU | Memory | Use Case |
|------|-----|--------|----------|
| Small | 0.25 vCPU | 0.5 Gi | Dev/test |
| Medium | 0.5 vCPU | 1.0 Gi | Staging, low-traffic prod |
| Large | 1.0 vCPU | 2.0 Gi | Production |
| XLarge | 2.0 vCPU | 4.0 Gi | High-load production |

---

## 3. Azure Cost Optimization Tips

### 3.1 Compute

- **Reserved Instances:** For predictable workloads, commit to 1- or 3-year reservations (up to 72% savings).
- **Spot/Preemptible:** Use for non-critical batch jobs where interruption is acceptable.
- **Scale to zero:** For staging/dev, set min replicas to 0 where possible.
- **Right-size ACA:** Start with 0.5 vCPU / 1 Gi; scale up only when metrics justify.

### 3.2 Database

- **Azure PostgreSQL:** Use Burstable tier for dev; General Purpose for prod. Monitor DTU/vCore utilization.
- **Connection pooling:** Use PgBouncer or app-level pooling to reduce connection count and allow smaller tiers.
- **Query optimization:** Slow queries increase CPU; use EXPLAIN ANALYZE and indexes.

### 3.3 Storage

- **Blob lifecycle:** Move cool/archive tiers for old logs and backups.
- **Delete unused disks:** Orphaned disks from deleted VMs/containers incur cost.
- **Log retention:** Reduce Application Insights and Log Analytics retention (e.g., 30–90 days).

### 3.4 Networking

- **Bandwidth:** Egress costs; minimize cross-region and internet egress.
- **VNet integration:** Use private endpoints to avoid data transfer charges where applicable.

### 3.5 Tagging & Governance

- **Tags:** Apply `Environment`, `Project`, `Owner` for cost allocation.
- **Budgets:** Create budgets per resource group or subscription (see §4).
- **Azure Policy:** Enforce tagging and prevent creation of expensive SKUs.

---

## 4. Budget Alert Response Procedures

### 4.1 Alert Thresholds

| Threshold | Meaning | Response |
|-----------|---------|----------|
| **50%** | Early warning | Review cost drivers; plan corrective action |
| **80%** | High risk | Immediate review; consider pausing non-essential resources |
| **100%** | Budget exceeded | Escalate; implement cost controls per approval |

### 4.2 50% Alert Response

1. **Acknowledge** alert within 4 hours.
2. **Review** Cost Management → Cost analysis for top spenders.
3. **Identify** any unexpected or new resources.
4. **Document** findings in runbook or ticket.
5. **Plan** adjustments (right-sizing, shutdown of dev resources) if trend suggests 80%+ by month-end.

### 4.3 80% Alert Response

1. **Acknowledge** alert within 2 hours.
2. **Escalate** to cost owner / platform lead.
3. **Immediate actions** (if approved):
   - Stop non-production Container Apps (scale to 0).
   - Pause dev/test databases outside business hours.
   - Review and cancel unused resources.
4. **Forecast** month-end spend; request budget increase if justified.

### 4.4 100% Alert Response

1. **Acknowledge** immediately.
2. **Escalate** to budget owner and leadership.
3. **Document** root cause (new project, spike, misconfiguration).
4. **Implement** controls per governance approval (e.g., cap non-essential spend).
5. **Update** budget or request exception for next period.

### 4.5 Setting Up Budget Alerts

Use `scripts/infra/azure_cost_alert.sh`:

```bash
# Default $500/month, thresholds at 50%, 80%, 100%
./scripts/infra/azure_cost_alert.sh

# Custom budget
./scripts/infra/azure_cost_alert.sh --budget 1000

# With specific email recipients
./scripts/infra/azure_cost_alert.sh --budget 500 --emails ops@example.com finance@example.com

# Scope to resource group
./scripts/infra/azure_cost_alert.sh --budget 200 --resource-group rg-qgp-staging

# Preview only (dry-run)
./scripts/infra/azure_cost_alert.sh --dry-run
```

**Note:** Budget evaluation runs every 24 hours. Alerts typically arrive within an hour of threshold evaluation.

---

## 5. Capacity Planning Worksheet

### 5.1 Monthly Cost Trend

Sample figures aligned with `docs/infra/cost-controls.md` (~£110–£160/mo total envelope). Replace with Azure Cost Management exports during the monthly review.

| Month | Budget | Actual | Variance | Notes |
|-------|--------|--------|----------|-------|
| 2026-01 | £130 | £125 | −£5 (−3.8%) | Within baseline envelope |
| 2026-02 | £130 | £142 | +£12 (+9.2%) | Spike review — compare to top services in portal |
| 2026-03 | £135 | £118 | −£17 (−12.6%) | Illustrative; confirm against billing |

### 5.2 Resource Inventory

| Resource | Environment | Current Size | Utilization (CPU/Mem) | Planned Change |
|----------|-------------|--------------|------------------------|----------------|
| App Service (API / backend) | Production | B2 | CPU ~35%, Mem ~45% | Right-size per §2 when 7-day averages stable |
| App Service (API / backend) | Staging | B1 (see cost-controls) | CPU ~20%, Mem ~30% | Align with pre-prod load |
| PostgreSQL Flexible Server | Production | B1ms | vCPU ~25%, Storage ~5GB/32GB | Storage alert >80% → extend/archive |
| PostgreSQL Flexible Server | Staging | B1ms (or lower burstable) | vCPU ~10%, Storage ~2GB/32GB | Match staging fidelity needs |
| Redis | Production | Basic C0 | Memory ~35% | Scale if sustained >60% memory |
| Azure Static Web Apps | Production | Free | N/A | Upgrade tier only if limits hit |
| Blob Storage | Production | Hot / LRS | N/A — capacity | Lifecycle to Cool per cost-controls |

### 5.3 Growth Assumptions

Planning assumes **100** active users today, **500** as the target scale, and **linear** growth between them unless product milestones dictate a step change. Replace projections with product/usage forecasts each quarter.

| Factor | Current | 3-Month | 6-Month | 12-Month |
|--------|---------|---------|---------|----------|
| Active users | 100 | ~200 (linear) | ~300 (linear) | 500 (target) |
| API requests/day | ~5,000 (App Insights baseline) | ~10,000 (linear with users) | ~15,000 (interpolated) | ~25,000 (re-baseline at 500 users) |
| Data volume (GB) | ~2GB (PostgreSQL) + ~1GB (Blob) | ~4GB + ~2GB | ~6GB + ~3GB | Capacity review before 500 users |
| Estimated monthly cost | £110–£160 (see cost-controls) | Trend with usage; watch compute + DB | Interpolate | Re-evaluate SKUs at target load |

### 5.4 Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-21 | Established FinOps baseline per cost-controls.md | Single reference for inventory, ~£110–£160/mo envelope, and optimisation controls (`docs/infra/cost-controls.md`) |

---

## 6. Quick Reference

| Task | Command / Location |
|------|--------------------|
| Cost analysis | Azure Portal → Cost Management → Cost analysis |
| Budget setup | `scripts/infra/azure_cost_alert.sh` |
| Autoscale config | `scripts/infra/autoscale_aca.sh` |
| Scaling guidance | `docs/ops/SCALING_PLAYBOOK.md` |
| Incident response | `docs/ops/INCIDENT_RESPONSE_RUNBOOK.md` |
