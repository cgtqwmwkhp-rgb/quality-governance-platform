# Disaster Recovery Plan (D05 — Reliability & Resilience)

This document describes recovery objectives, backups, failover, chaos practices, circuit breaking, graceful degradation, and verification for the Quality Governance Platform.

## RPO / RTO Targets

| Metric | Target | Notes |
|--------|--------|--------|
| **RPO** | **1 hour** | PostgreSQL **point-in-time recovery (PITR)** — acceptable maximum data loss window for transactional data. |
| **RTO** | **30 minutes** | Time to restore service to a defined minimum acceptable capability after a major failure. |

## Backup Strategy

| Component | Strategy |
|-----------|----------|
| **PostgreSQL** | **Azure automated daily backups** plus **point-in-time restore** within the retention window. Test restores periodically. |
| **Redis** | **AOF persistence** (and/or RDB as configured in Azure Cache for Redis) — treat as cache/session layer; design for rebuild from source of truth where possible. |
| **Blob storage** | **Geo-redundant** storage (e.g., GRS/RA-GRS as appropriate) for artifacts and user blobs. |

## Failover Procedures

### Database failover

1. Confirm outage scope in Azure Portal (replica lag, region issue).
2. Initiate **planned or automatic failover** per Azure PostgreSQL guidance; update connection strings if endpoints change.
3. Verify `/readyz` and run **recovery verification** checks below.

### Redis reconnection

1. After Redis is healthy, restart app/workers in a **staggered** manner to avoid connection storms.
2. Validate Celery broker and result backend connectivity.
3. Monitor error rate and cache miss ratio until stable.

### App Service restart

1. Use **slot** or rolling restart if available to reduce blast radius.
2. Confirm `/healthz` then `/readyz` after restart.
3. Watch Azure Monitor for error/latency regression.

## Chaos Engineering Plan

Run **quarterly failure-injection exercises** in a non-production environment (or controlled production windows with approval):

- **Kill instance** — terminate/restart a single app instance; validate auto-heal and load distribution.
- **DB failover** — exercise PostgreSQL failover; measure RTO and connection handling.
- **Network partition simulation** — block Redis or external APIs; validate timeouts, circuit breakers, and user-visible degradation.

Document findings, action items, and track remediation in the engineering backlog.

## Circuit Breaker Configuration

Implementation: `src/infrastructure/resilience/circuit_breaker.py` (`CircuitBreaker`).

| Parameter | Default | Behavior |
|-----------|---------|----------|
| `failure_threshold` | **5** | Consecutive failures in the **CLOSED** state required to **OPEN** the circuit. |
| `recovery_timeout` | **60.0** seconds | After OPEN, time before the breaker allows **HALF_OPEN** trial calls. |
| `half_open_max_calls` | **1** | Maximum trial calls allowed in **HALF_OPEN** before rejecting further calls until recovery. |

Related: `retry_with_backoff` in the same module (default `max_retries=3`, `base_delay=0.5`, `max_delay=30.0`) for transient errors **before** failures count toward breaker behavior in integrated call paths.

Operational note: breaker state transitions emit metrics via `track_metric` (`circuit_breaker.<name>.transition`, `circuit_breaker.<name>.state`, `circuit_breaker.<name>.total_failures`) when Azure Monitor integration is available.

## Graceful Degradation Matrix

| Dependency | If unavailable / degraded | Fallback behavior |
|------------|---------------------------|-------------------|
| **PAMS** (external) | Timeouts or circuit OPEN | Serve cached read data where safe; queue writes for retry; return user-visible “temporarily unavailable” for PAMS-only features; do not block core CRUD that does not require PAMS. |
| **Redis** | Connection failures / evictions | Degrade to **direct DB** for session/token paths where implemented; disable non-critical caching; throttle expensive endpoints; surface reduced performance, not hard failure where possible. |
| **Blob** | Storage errors / auth | Retry with backoff; return clear error for upload/download; allow in-app flows that do not require blob to continue. |

Exact behavior should match product requirements; update this matrix when integrations change.

## Recovery Verification

After failover, restore, or major incident mitigation:

1. **Post-failover smoke tests**: `/healthz`, `/readyz`, login (if applicable), one read and one write API path, one Celery job path.
2. **Data integrity checks**: Spot-check critical tables vs. expected counts; reconcile blob metadata if used transactionally with DB.
3. **Version check**: `/api/v1/meta/version` matches intended release.
4. **Monitor**: 30–60 minutes of green dashboards before closing the incident.
