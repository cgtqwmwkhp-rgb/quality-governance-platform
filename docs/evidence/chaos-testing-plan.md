# Chaos Testing Plan (D05)

Planned failure injection scenarios for reliability validation.

## Objective

Validate system resilience by deliberately introducing failures in controlled conditions, confirming graceful degradation and recovery.

## Failure Scenarios

| # | Scenario | Component | Expected Behavior | Priority |
|---|----------|-----------|-------------------|----------|
| 1 | Database connection pool exhaustion | PostgreSQL | API returns 503; health check fails; auto-recovery on pool refresh | P0 |
| 2 | Redis unavailability | Rate limiter / cache | Rate limiting falls back to in-memory; idempotency uses DB fallback | P0 |
| 3 | Blob storage timeout | Azure Blob | Evidence upload returns error; existing assets still readable via cache | P1 |
| 4 | App Service instance crash | Compute | Load balancer routes to healthy instance; auto-restart within 60s | P0 |
| 5 | Database failover | PostgreSQL | Connections re-established; brief 503 window; no data loss | P1 |
| 6 | Network partition (API ↔ DB) | Network | API returns 503; circuit breaker prevents cascade | P2 |
| 7 | Disk full on App Service | Compute | Log rotation prevents full disk; alert fires before critical | P2 |

## Rollback Drills

| Drill | Last Run | Result | Next Scheduled |
|-------|----------|--------|----------------|
| Production rollback via slot swap | 2026-03-15 | Successful — 8s swap time | 2026-06-15 |
| Database point-in-time restore | TBD | Not yet conducted | 2026-Q2 |

## Execution Framework

1. **Environment**: Staging only (never production for chaos tests)
2. **Notification**: Team notified 24h before scheduled chaos test
3. **Duration**: Each scenario runs for max 5 minutes
4. **Monitoring**: Azure Monitor + application logs during test window
5. **Post-mortem**: Document results, unexpected behaviors, and remediation actions

## Related Documents

- [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) — incident response
- [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md) — rollback procedures
