# Runbook: Database connection pool exhaustion

## Summary

SQLAlchemy/async pool saturation or PostgreSQL connection pressure causes the API to wait on connections, return errors, or time out. This runbook covers **detection**, **immediate mitigation**, and **follow-up**.

## Symptoms

- **HTTP 503** (or 500) from API instances; elevated latency across routes.
- Application logs showing SQLAlchemy pool errors, e.g. **`QueuePool limit of N overflow M reached`** (or similar “could not obtain connection” messages).
- Correlated spikes in dependency duration and thread/async wait time.

## Detection

| Signal | Action |
|--------|--------|
| **`db.pool_usage_percent`** | Investigate when **> 80%** sustained; capacity is tightening. |
| **Formal alert** | See **[Alerting rules](../observability/alerting-rules.md)** — **DB connection pool exhaustion**: active connections **≥ 90%** of pool max for **3 minutes**, or elevated “unable to acquire connection” log rate → **P1**, runbook `runbooks/db-pool-exhaustion.md`. |

Confirm on dashboards: connections in use vs max, error rate, and slow queries (see [Observability: dashboards](../observability/alerting-rules.md#dashboard-definitions)).

## Impact

- **All API endpoints** that touch the database may **degrade** (slow responses, timeouts, 5xx).
- Risk of **cascade failure** (retries, queue buildup, client thundering herd) if not contained.

## Immediate response

1. **Check live connection count** (PostgreSQL; database name **`qgp_production`**):

   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'qgp_production';
   ```

2. **Identify long-running or blocking queries**:

   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY duration DESC
   LIMIT 10;
   ```

3. **Terminate stuck backends** only when justified (idle in transaction, old enough). Example: idle-in-transaction older than 5 minutes on `qgp_production`:

   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE datname = 'qgp_production'
     AND state = 'idle in transaction'
     AND query_start < now() - interval '5 minutes';
   ```

   Prefer coordinating with DBA / change window for production; document PIDs and queries in the incident.

4. **Scale the pool** (requires deploy / restart):
   - If your deployment maps pool size to environment variables (e.g. **`POOL_SIZE`** / **`DB_POOL_SIZE`**), **increase cautiously** (avoid exceeding PostgreSQL `max_connections` across all app instances).
   - **Restart** affected app instances after changing pool-related configuration so new limits apply.

   Current application defaults are defined in code — see **Configuration reference** below.

5. **Reduce load** if needed: scale out app instances, enable rate limiting, or temporarily shed non-critical traffic per incident policy.

## Root cause investigation (checklist)

- [ ] **Traffic**: unusual spike, new client, or batch job?
- [ ] **Deploy**: recent release changing query patterns, N+1 queries, or missing indexes?
- [ ] **Slow queries**: `pg_stat_statements` / slow query log; `EXPLAIN (ANALYZE)` on worst offenders.
- [ ] **Connection leaks**: sessions not closed, long-held transactions, background tasks without proper teardown.
- [ ] **Pool vs instances**: total app connections = instances × workers × effective pool usage; compare to DB `max_connections`.
- [ ] **Locks / blocking**: other sessions holding locks (investigate `pg_locks`, blocking chains).
- [ ] **Infrastructure**: DB CPU, I/O, or network saturation masquerading as pool wait.

## Prevention

| Area | Recommendation |
|------|----------------|
| **Timeouts** | Keep **connection checkout** and **statement** timeouts appropriate so failures fail fast; see code defaults below (`pool_timeout`, server `statement_timeout`). |
| **`pool_pre_ping`** | Enabled for PostgreSQL async engine — validates connections before use (avoids stale connections after idle). |
| **`pool_recycle`** | Recycle connections periodically to avoid long-lived bad server-side state (see code). |
| **ORM / app** | Short transactions; avoid “idle in transaction”; use request-scoped sessions; fix leaks in Celery/async tasks. |
| **Capacity** | Size pool and instance count against load tests and [Performance SLOs](../slo/performance-slos.md). |

## Configuration reference

Async SQLAlchemy engine pool settings for **PostgreSQL** (non-test) are in **`src/infrastructure/database.py`** (excerpt):

```python
# src/infrastructure/database.py — engine_kwargs.update(...) for postgresql
{
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 1800,
    "pool_timeout": 30,
    "connect_args": {
        "server_settings": {"statement_timeout": "30000"},
    },
}
```

- **Effective async pool capacity** (baseline): `pool_size` + `max_overflow` = **10 + 20 = 30** connections per process using this engine.
- **Sync engine** (Celery): `create_engine(..., pool_pre_ping=True)` — default pool sizing applies unless overridden elsewhere; verify worker concurrency × pool when investigating.

If pool sizing is not yet driven by environment variables in your branch, update **`pool_size`** / **`max_overflow`** (and matching `_PG_POOL_SIZE` / `_PG_MAX_OVERFLOW` used for **`db.pool_usage_percent`**) in that module, then redeploy.

## Escalation

- **P1** handling per **[Alerting rules](../observability/alerting-rules.md)** (channels, severity).
- **[On-call guide](on-call-guide.md)** for rotation, handoff, and escalation expectations.
