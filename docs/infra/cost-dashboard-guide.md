# Azure Cost Dashboard Guide (D26)

How to set up and use Azure Cost Management for the Quality Governance Platform.

## Dashboard Setup

### Step 1: Access Cost Management

Navigate to **Azure Portal > Cost Management + Billing > Cost Management > Cost analysis**.

### Step 2: Create Custom Views

Create the following saved views:

| View Name | Group By | Filter | Granularity |
|-----------|----------|--------|-------------|
| QGP Monthly Overview | Service name | Tag: `service = qgp-*` | Monthly |
| QGP By Component | Tag: `service` | Tag: `cost-center = engineering` | Monthly |
| QGP By Environment | Tag: `environment` | Tag: `service = qgp-*` | Monthly |
| QGP Daily Burn Rate | Service name | Tag: `service = qgp-*` | Daily |

### Step 3: Configure Budget Alerts

Deploy the budget alert ARM template:

```bash
az deployment sub create \
  --location uksouth \
  --template-file scripts/infra/budget-alert.json
```

Alert thresholds:
- **80% (Warning)**: Email to platform-team
- **100% (Critical)**: Email to platform-team + engineering-lead

## Review Cadence

| Frequency | Activity | Owner |
|-----------|----------|-------|
| Weekly | Check daily burn rate view for anomalies | On-call engineer |
| Monthly | Full cost review meeting with Cost Analysis export | Platform Engineering |
| Quarterly | Right-sizing analysis, reserved instance evaluation | Platform Engineering |

## Key Metrics to Monitor

| Metric | Source | Expected Range |
|--------|--------|----------------|
| Total monthly spend | Cost Management | £110-£160 |
| App Service compute | Cost Management | £35-£65 |
| Database cost | Cost Management | £25-£40 |
| Storage cost | Cost Management | £1-£5 |
| CI minutes used | GitHub Settings | < 1500/2000 min |

## Anomaly Investigation

When a budget alert fires:

1. Check **Cost Analysis > Daily** view for the spike date
2. Filter by **Service name** to identify the cost driver
3. Check for: orphan resources, unexpected scale-out events, storage growth
4. Document findings in the monthly cost review notes
5. If action needed, follow the optimization checklist in `docs/infra/cost-controls.md`

## Related Documents

- [`docs/infra/cost-controls.md`](cost-controls.md) — cost controls and FinOps policy
- [`scripts/infra/budget-alert.json`](../../scripts/infra/budget-alert.json) — ARM budget template
- [`docs/infra/capacity-plan.md`](capacity-plan.md) — capacity planning
