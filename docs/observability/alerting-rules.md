# Observability: SLIs, Alerting, Dashboards, and Response (D13)

This document defines service level indicators, alert rules, dashboard layout, escalation timing, on-call expectations, and incident classification for the Quality Governance Platform.

## SLI definitions

| SLI | Definition | Target |
|-----|------------|--------|
| **Availability** | Percentage of HTTP requests that complete with status **200–399** (inclusive), excluding health probes that are documented as synthetic, measured per service and region | Meet error budget policy (see SLO doc); alert before sustained breach |
| **Latency** | **p99** request duration for API routes (server-side), excluding long-poll or export endpoints if labeled in monitoring | **p99 < 500 ms** under normal load |
| **Error rate** | Ratio of **5xx** responses to all non-health requests over a rolling window | **< 0.1%** (0.001) sustained; short spikes evaluated against burn rate |

Recording rules and burn-rate windows should align with the central metrics store (e.g. Prometheus/Grafana Mimir); implementation detail lives in infrastructure repos.

## Alert rules

| Alert | Condition | Severity | Channel | Runbook |
|-------|-----------|----------|---------|---------|
| **API error rate** | 5xx rate > 0.1% for **5 minutes** (or fast burn: > 0.3% for 2 minutes) on primary API | P2 | `#platform-alerts` + PagerDuty (business hours) | `runbooks/api-error-rate.md` — identify deploy vs dependency; roll back or scale; check recent migrations |
| **API error rate (critical)** | 5xx rate > 1% for **2 minutes** or availability &lt; 95% for **5 minutes** | P1 | PagerDuty immediate + `#platform-incidents` | `runbooks/api-outage.md` — incident commander; enable maintenance page if needed |
| **DB connection pool exhaustion** | Active connections ≥ **90%** of pool max for **3 minutes**, or “unable to acquire connection” log rate &gt; threshold | P1 | PagerDuty + `#data-platform` | `runbooks/db-pool-exhaustion.md` — kill runaway queries, scale pool cautiously, review connection leaks |
| **Redis disconnection** | Redis **unreachable** or command error rate spike for **2 minutes** (cache/session broker) | P2 | `#platform-alerts` + PagerDuty (if session-critical) | `runbooks/redis-disconnection.md` — failover, check TLS/auth, broker memory |
| **Celery queue depth** | Queue depth &gt; **N** (documented per queue) for **10 minutes**, or age-of-oldest-task &gt; **S** seconds | P2 | `#platform-alerts` | `runbooks/celery-queue-depth.md` — scale workers, inspect stuck tasks, dead letter handling |
| **Celery queue depth (critical)** | Depth &gt; **2× N** or oldest task &gt; **2× S** | P1 | PagerDuty | `runbooks/celery-backlog-critical.md` |
| **Auth failure spike** | Failed logins / invalid token rate &gt; **3×** baseline (rolling 15m) for **10 minutes**, or same source IP volume anomaly | P2 | `#security-ops` + `#platform-alerts` | `runbooks/auth-failure-spike.md` — WAF rules, credential stuffing checklist, IdP status |
| **Auth failure spike (suspected attack)** | Global auth failure rate &gt; **10×** baseline or geo anomaly per SIEM | P1 | PagerDuty + `#security-incidents` | `runbooks/credential-attack.md` |
| **Certificate expiry** | TLS certificate **expires in ≤ 14 days** (warning), **≤ 7 days** (page), **≤ 2 days** (critical) | P3 (14d) / P2 (7d) / P1 (2d) | Email + `#platform-alerts`; PagerDuty for ≤7d | `runbooks/certificate-renewal.md` — renew via ACME/secret manager, verify chain |
| **Disk usage** | Root or data volume **&gt; 85%** (warning), **&gt; 90%** (critical), sustained **10 minutes** | P3 / P2 | `#platform-alerts`; PagerDuty at 90% on prod nodes | `runbooks/disk-usage.md` — logs, uploads, image GC, expand volume |

Tune thresholds (N, S, baselines) per environment in the monitoring configuration; this table is the **contract** for what must exist.

## Dashboard definitions

### 1. Platform Health

**Purpose**: Live picture of uptime and dependencies.

**Key panels**

- Availability (200–399 %) and 5xx rate by service
- Pod / instance count and restarts
- Database: connections in use, max connections, slow query count
- Redis: connected clients, evictions, memory
- Celery: workers alive, queue depth by queue
- Disk and memory per node class

### 2. API Performance

**Purpose**: Latency, throughput, and saturation for APIs.

**Key panels**

- Request rate by route (top N)
- p50 / p95 / p99 latency by route
- Error rate by status class (4xx vs 5xx)
- Upstream dependency latency (DB, Redis, HTTP clients)
- Rate limiting and timeout counters

### 3. Business Metrics

**Purpose**: Product usage and workflow health (governance-specific).

**Key panels**

- Active organizations and daily active users (if tracked)
- Incidents / risks / RTAs / complaints created and closed (rates)
- Audit completions and overdue actions
- Notification delivery success vs failure
- Export / report job success rate

### 4. Security

**Purpose**: Auth, certificates, and abuse signals.

**Key panels**

- Auth success vs failure rate; failures by reason
- Token validation errors and refresh failures
- Certificate days-to-expiry (min across ingress)
- WAF / rate-limit blocks (if applicable)
- Geo and ASN breakdown for auth anomalies (privacy-preserving aggregation)

## Escalation matrix

| Priority | First response | Notes |
|----------|----------------|--------|
| **P1** | **15 minutes** | All hands until mitigated; war room optional |
| **P2** | **1 hour** | Owner acknowledges; fix or escalate within SLA |
| **P3** | **4 hours** | Business-hours handling unless merged with security |
| **P4** | **Next business day** | Track in backlog; no paging |

Escalation steps (L1 → L2 → management) are defined in `runbooks/escalation-policy.md` (repository link or wiki).

## On-call rotation

- **Schedule**: Maintained in the team **on-call calendar** (e.g. PagerDuty / Opsgenie / Google Calendar)—see link in the team wiki under *Engineering → On-call*.
- **Handoff**: At rotation boundary, outgoing on-call posts a **handoff note** in `#platform-incidents` (or tool equivalent): open incidents, noisy alerts, deploys in flight, and any manual mitigations.
- **Expectations**: On-call carries laptop, has VPN and prod read access, and follows runbooks before escalating.

## Incident classification (user impact)

| Priority | User impact |
|--------|-------------|
| **P1** | **Total outage** or equivalent: majority of users cannot perform core workflows; data loss or integrity risk; security incident with active exploitation |
| **P2** | **Degraded**: significant slowdowns, partial feature failure, or elevated error rates affecting many users; workaround may exist |
| **P3** | **Minor**: limited subset of users or non-critical features affected; no major SLA breach |
| **P4** | **Cosmetic** or low-impact: UI glitches, non-blocking bugs, internal-only tooling |

Severity at open may be **reclassified** after impact assessment; customer communications follow the comms playbook.
