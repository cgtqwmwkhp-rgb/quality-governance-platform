# Alerting Integration Runbook (D23)

Setup and configuration for production alerting.

## Current Alerting Stack

| Component | Service | Status |
|-----------|---------|--------|
| Cost alerts | Azure Cost Management | Active |
| Health check monitoring | Azure App Service | Active |
| Log-based alerts | Azure Log Analytics | Partial |
| Incident paging | PagerDuty | Planned |
| Team notifications | Slack/Teams | Planned |

## Azure Monitor Alert Rules

### Active Rules

| Rule | Resource | Condition | Action Group |
|------|----------|-----------|--------------|
| Health check failure | App Service (prod) | HTTP 5xx > 5 in 5 min | Email: platform-team |
| High CPU | App Service (prod) | CPU > 80% for 15 min | Email: platform-team |
| DB storage warning | PostgreSQL | Storage > 80% | Email: platform-team |
| Budget warning | Subscription | Cost > 80% of $500 | Email: platform-team |
| Budget critical | Subscription | Cost > 100% of $500 | Email: platform-team + eng-lead |

### Planned Rules

| Rule | Trigger | Target Action Group |
|------|---------|---------------------|
| API p95 > 200ms (15 min) | OpenTelemetry metrics | PagerDuty (high) |
| API p99 > 500ms (15 min) | OpenTelemetry metrics | PagerDuty (critical) |
| Error rate > 1% (5 min) | Application logs | PagerDuty (high) |
| Failed deployments | GitHub Actions webhook | Slack notification |

## PagerDuty Setup Plan

### Prerequisites
1. PagerDuty account provisioned
2. Service created: "QGP Production"
3. Escalation policy defined (see below)
4. Azure Monitor integration configured

### Escalation Policy

| Level | Wait Time | Notify |
|-------|-----------|--------|
| L1 | Immediate | On-call engineer |
| L2 | 15 minutes | Engineering lead |
| L3 | 30 minutes | Platform manager |

### Integration Steps

1. Create PagerDuty service and obtain integration key
2. Create Azure Monitor Action Group with PagerDuty webhook
3. Associate Action Group with alert rules
4. Test end-to-end: trigger test alert → verify PagerDuty incident

## Slack/Teams Notification Plan

| Event | Channel | Priority |
|-------|---------|----------|
| Deployment started | #deployments | Info |
| Deployment completed | #deployments | Info |
| Deployment failed | #alerts | High |
| Alert fired | #alerts | High |
| PR merged to main | #deployments | Info |

## Related Documents

- [`docs/observability/alerting-rules.md`](../observability/alerting-rules.md) — SLO alerting rules
- [`docs/runbooks/on-call-guide.md`](on-call-guide.md) — on-call procedures
- [`docs/observability/telemetry-enablement-plan.md`](../observability/telemetry-enablement-plan.md) — telemetry plan
