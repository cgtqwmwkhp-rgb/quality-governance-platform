# On-Call Guide (D23 — Operational Runbooks)

This guide defines how on-call engineers monitor the Quality Governance Platform, respond to alerts, and hand off shifts.

## On-Call Responsibilities

- **Monitor dashboards**: Keep Azure Monitor / application dashboards visible during the shift; watch error rates, latency, queue depth, and dependency health.
- **Respond to alerts**: Acknowledge pages and notifications within the SLA for the severity tier; begin triage within minutes for P1/P2.
- **Triage incidents**: Determine scope (customer impact, blast radius), identify failing component (API, worker, DB, cache), open or update the incident channel, and apply mitigations or escalate as needed.

## Alert Response Playbook

### API errors

1. Check `/healthz` and `/readyz` to confirm process vs. dependency health.
2. Review recent deployments and GitHub Actions runs for a bad release.
3. Inspect application logs in Azure Monitor for stack traces and correlated `request_id`.
4. If errors cluster on specific routes, check upstream config (auth, feature flags) and downstream calls (PAMS, DB, Redis).
5. Scale or restart the App Service only after ruling out code/config issues; capture thread dumps if the process is wedged.

### Database (PostgreSQL) issues

1. Confirm `/readyz` reports database connectivity; if not, check Azure PostgreSQL status and firewall/private endpoint.
2. Review connection pool metrics and active sessions; look for pool exhaustion or long-running queries.
3. Check for failover events, storage full, or maintenance windows in Azure Portal.
4. If migrations failed, see `docs/ops/troubleshooting-guide.md` (Database Troubleshooting) before re-running.
5. Escalate to DBA/platform if storage, replication, or server parameters need change.

### Redis

1. Verify Redis endpoint reachability from the app subnet / VNet integration.
2. Check memory usage, eviction policy, and connection counts in Azure Cache for Redis metrics.
3. Review Celery/worker logs for `ConnectionError` / timeout bursts.
4. If Redis is degraded, consider brief app restart after Redis is healthy; ensure no thundering herd (stagger workers).

### Celery (workers / async tasks)

1. Confirm Redis and broker URLs; inspect queue depth and worker heartbeat in monitoring.
2. Check worker process count and OOM/restart events on the worker host or container.
3. Identify stuck tasks: poison messages, deadlocks, or external API timeouts.
4. Scale workers temporarily for backlog burn-down after root cause is understood.
5. Disable or rate-limit problematic task types only with product/engineering agreement.

## Escalation Paths

| Priority | Definition (typical) | Escalation |
|----------|----------------------|------------|
| **P1** | Full or critical-path outage; data loss or security incident | **Immediate page** on-call + engineering lead + comms owner |
| **P2** | Major degradation; workaround exists | **Slack** incident channel + **email** to stakeholders |
| **P3** | Limited impact; no immediate customer blocker | Discuss at **next standup**; track in backlog ticket |
| **P4** | Cosmetic, minor, or internal-only | **Backlog**; no on-call wake-up |

## Shift Handoff Checklist

Outgoing on-call should brief incoming on-call on:

- [ ] **Active incidents**: ID, severity, current mitigations, next actions, comms status
- [ ] **Pending deployments**: In staging or production; SHA; who owns the promotion
- [ ] **Known issues**: Flapping alerts, tech debt affecting stability, recent near-misses
- [ ] **Upcoming maintenance**: Azure maintenance, certificate expiry, planned releases

## Communication Templates

### Customer notification (outage)

**Subject**: [Service] — Service disruption — investigating

We are investigating reports of elevated errors / unavailable functionality affecting [product area]. Our team is actively working to restore normal service. We will update this message within [60] minutes or sooner as we learn more.

**Optional**: Status page link, support contact, scope (“login may be affected”).

### Internal status update

**Incident**: [INC-xxx]  
**Severity**: P[1–4]  
**Status**: Investigating | Mitigating | Monitoring | Resolved  
**Impact**: [who/what is affected]  
**What we know**: [1–3 bullets]  
**Next update**: [time or event]  
**On-call**: [name]

## Post-Incident Review

- **Blameless retrospective** scheduled and completed **within 48 hours** of resolution or significant mitigation.
- **Root cause analysis (RCA)** document delivered **within 5 business days**, including timeline, contributing factors, corrective actions, and preventive measures.

## Reference Links

| Resource | URL / path |
|----------|------------|
| Liveness | `/healthz` |
| Readiness (dependencies) | `/readyz` |
| Runtime / resource metrics | `/metrics/resources` |
| Azure Portal | https://portal.azure.com |
| GitHub Actions | Repository → **Actions** tab (CI/CD workflows) |
