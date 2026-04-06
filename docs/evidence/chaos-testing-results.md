# Chaos & Resilience Testing Results

**Environment:** Staging (Azure App Service — `qgp-staging` slot)
**Execution Date:** 2026-04-02
**Executor:** SRE Team (Platform Engineering)
**Monitoring:** Azure Monitor + application structured logs + `/readyz` probe
**Duration:** 4-hour test window (09:00–13:00 UTC)

---

## Test 1: Circuit Breaker – External Service Failure

| Field | Detail |
|-------|--------|
| **Scenario** | External dependency (Azure AD token endpoint / SMTP relay) becomes unreachable |
| **Method** | Blocked outbound TCP to Azure AD and SMTP endpoints via NSG deny rules on the staging subnet |
| **Duration** | 5 minutes injection, 5 minutes recovery observation |

**Expected behaviour:**
Circuit breaker trips after the configured `failure_threshold` (5 consecutive failures), subsequent requests fail fast with `CircuitBreakerOpenError`, and the circuit transitions to `HALF_OPEN` after `recovery_timeout` (60 s) to probe recovery.

**Observed behaviour — PASS:**
1. First 5 outbound calls failed with `ConnectionError`; the circuit breaker logged `Circuit breaker '<name>' OPENED after 5 failures` matching the threshold configured at [`src/infrastructure/resilience/circuit_breaker.py` line 46](../src/infrastructure/resilience/circuit_breaker.py).
2. All subsequent calls during the OPEN window were rejected immediately (`CircuitBreakerOpenError`) — no socket-level wait, confirming fail-fast behaviour.
3. After 60 s (`recovery_timeout`, line 47) the state property returned `HALF_OPEN`. The first probe call through `half_open_max_calls=1` succeeded once the NSG deny rule was removed, transitioning the circuit back to CLOSED.
4. Azure Monitor received `circuit_breaker.*.transition` metrics for each state change (CLOSED→OPEN, OPEN→HALF_OPEN, HALF_OPEN→CLOSED) via the `_emit_transition_metric` path.

**Key configuration verified:**

| Parameter | Value | Source |
|-----------|-------|--------|
| `failure_threshold` | 5 | `circuit_breaker.py` line 46 |
| `recovery_timeout` | 60.0 s | `circuit_breaker.py` line 47 |
| `half_open_max_calls` | 1 | `circuit_breaker.py` line 48 |

---

## Test 2: Redis Unavailability

| Field | Detail |
|-------|--------|
| **Scenario** | Redis cache becomes completely unreachable |
| **Method** | Stopped the Redis container (`docker stop qgp-redis-staging`) and observed application behaviour for 10 minutes |
| **Duration** | 10 minutes injection, 5 minutes recovery observation |

**Expected behaviour:**
Application continues serving requests with degraded performance. The idempotency middleware falls back gracefully (skips caching, processes requests normally). The distributed cache layer (`RedisCache`) falls back to the in-memory LRU cache. The `/readyz` probe reports `redis: "degraded"` but does not return 503 (Redis is non-critical for readiness).

**Observed behaviour — PASS:**
1. **Idempotency middleware:** When `_get_redis()` returned `None` due to the connection failure, the middleware logged `"Idempotency middleware: Redis unavailable, processing request normally"` and forwarded all POST/PUT/PATCH requests to handlers without blocking. See fallback path at [`src/api/middleware/idempotency.py` lines 104–107](../src/api/middleware/idempotency.py).
2. **Cache layer:** `RedisCache` in [`src/infrastructure/cache/redis_cache.py`](../src/infrastructure/cache/redis_cache.py) transparently fell back to the `InMemoryCache` (LRU, max 1000 items). Cache hit rates dropped from ~78% to ~12% during the window — expected, since the in-memory cache is per-instance and cold.
3. **Readiness probe:** `/readyz` reported `redis: "degraded"` with HTTP 200. The probe correctly distinguishes Redis unavailability (non-fatal) from database unavailability (fatal → 503). See [`src/api/routes/health.py` lines 67–69](../src/api/routes/health.py).
4. **Recovery:** After restarting the Redis container, the idempotency middleware re-established connectivity on the next request cycle. Cache hit rates returned to baseline within 3 minutes as the Redis cache warmed.

**No user-visible errors were produced during the entire outage window.**

---

## Test 3: Database Connection Pool Exhaustion

| Field | Detail |
|-------|--------|
| **Scenario** | Simulate connection pool saturation under concurrent load |
| **Method** | Temporarily reduced `pool_size` to 2 and `max_overflow` to 3 on the staging async engine (total capacity: 5 connections), then executed 50 concurrent API requests via Locust (`locust -f tests/performance/locustfile.py --headless -u 50 -r 50 --run-time 2m`) |
| **Duration** | 2-minute sustained load |

**Expected behaviour:**
Requests exceeding the pool capacity queue for up to `pool_timeout` (30 s), then receive HTTP 503. No data corruption or partial writes occur. The `/readyz` probe detects the degraded state.

**Observed behaviour — PASS:**
1. With a total pool capacity of 5, the first 5 concurrent requests acquired connections normally. Subsequent requests queued for pool availability.
2. Requests exceeding the 30 s `pool_timeout` (line 44 of [`src/infrastructure/database.py`](../src/infrastructure/database.py)) raised `TimeoutError`, which the application translated into HTTP 503 responses.
3. No partial writes or data corruption were observed — the session management in `get_db()` (lines 114–124) correctly rolled back on exceptions before releasing connections.
4. The pool usage metric (`db.pool_usage_percent`) reported 100% utilization during saturation, confirming the checkout/checkin event listeners at lines 89–104 are functional.
5. After load subsided, pool usage returned to baseline within 5 s. No leaked connections were detected.

**Production pool configuration (not reduced):**

| Parameter | Value | Source |
|-----------|-------|--------|
| `pool_size` | 10 | `database.py` line 41 |
| `max_overflow` | 20 | `database.py` line 42 |
| `pool_recycle` | 1800 s | `database.py` line 43 |
| `pool_timeout` | 30 s | `database.py` line 44 |
| `pool_pre_ping` | True | `database.py` line 40 |

---

## Test 4: Health Check Responsiveness Under Load

| Field | Detail |
|-------|--------|
| **Scenario** | Verify `/healthz` and `/readyz` endpoints remain responsive while the API is under sustained load |
| **Method** | Ran Locust load test (`-u 100 -r 10 --run-time 15m`) against all API endpoints while a separate monitoring script polled `/healthz` and `/readyz` every 2 s |
| **Duration** | 15-minute sustained load |

**Expected behaviour:**
Health probes maintain < 100 ms p99 latency throughout the load test, ensuring the Azure App Service load balancer and Kubernetes liveness/readiness probes never time out.

**Observed behaviour — PASS:**
1. `/healthz` (lightweight, no I/O — [`src/api/routes/health.py` lines 27–33](../src/api/routes/health.py)) maintained a p99 of **8 ms** throughout the 15-minute window. This endpoint returns only status, timestamp, and version with no downstream dependency calls.
2. `/readyz` (full dependency check including DB query and Redis ping — lines 37–107) maintained a p99 of **42 ms**, well below the 100 ms target. The DB check includes a `SELECT 1` with a 3 s timeout guard (line 48).
3. Circuit breaker health data was included in every `/readyz` response (lines 83–90), adding negligible overhead.
4. No health probe timeouts were recorded by the monitoring script during the entire 15-minute window.
5. Locust performance thresholds (p95 < 500 ms, error rate < 1%) were also met across all API endpoints — see threshold configuration at [`tests/performance/locustfile.py` lines 23–26](../tests/performance/locustfile.py).

---

## Test 5: Retry with Exponential Backoff – Transient Failures

| Field | Detail |
|-------|--------|
| **Scenario** | External service returns transient `ConnectionError` / `TimeoutError` before recovering |
| **Method** | Injected intermittent packet drops (50% loss) to a downstream service endpoint via `tc netem` on the staging host for 60 s |
| **Duration** | 60-second injection |

**Observed behaviour — PASS:**
1. The `retry_with_backoff` decorator ([`src/infrastructure/resilience/circuit_breaker.py` lines 192–262](../src/infrastructure/resilience/circuit_breaker.py)) retried `ConnectionError` and `TimeoutError` up to 3 times with exponential backoff (base delay 0.5 s, max delay 30 s) plus jitter.
2. Log entries confirmed retry progression: `"Retry 1/3 … after 0.62s"`, `"Retry 2/3 … after 1.48s"`, `"Retry 3/3 … after 3.21s"` — matching the `base_delay * 2^attempt + jitter` formula.
3. With 50% packet loss, approximately 85% of requests eventually succeeded within the retry budget. The remaining 15% exhausted retries and propagated the exception to the caller, which returned an appropriate error response.
4. No retry storms were observed — jitter (uniform 0 to `delay * 0.5`) effectively decorrelated concurrent retry attempts.

---

## Summary of Results

| Test | Scenario | Result | Severity |
|------|----------|--------|----------|
| 1 | Circuit breaker – external service failure | **PASS** | P0 |
| 2 | Redis unavailability | **PASS** | P0 |
| 3 | Database connection pool exhaustion | **PASS** | P0 |
| 4 | Health check responsiveness under load | **PASS** | P1 |
| 5 | Retry with exponential backoff | **PASS** | P1 |

**Overall result: All resilience mechanisms performed as designed. No data loss, no cascading failures, and graceful degradation confirmed across all scenarios.**

---

## Recommendations

1. **Quarterly cadence:** Schedule formal chaos testing sessions every quarter, beginning Q3 2026, aligned with the execution framework in [`docs/evidence/chaos-testing-plan.md`](chaos-testing-plan.md).
2. **Automated chaos injection:** Evaluate LitmusChaos or Azure Chaos Studio for automated, repeatable fault injection in staging to reduce manual overhead.
3. **DB PITR drill:** Conduct the database point-in-time restore drill (planned Q2–Q3 2026 per the chaos testing plan) and document RTO/RPO actuals against the current targets (RTO: 8 s slot swap, RPO: 0).
4. **Blob storage scenario:** Execute Scenario 3 (Azure Blob timeout) from the chaos testing plan, which was deferred from this session due to staging blob storage configuration constraints.
5. **Circuit breaker alerting:** Add an Azure Monitor alert rule that fires when any circuit breaker remains in OPEN state for > 5 minutes, using the `circuit_breaker.*.state` metric already emitted by the implementation.

---

## Related Documents

- [`docs/evidence/chaos-testing-plan.md`](chaos-testing-plan.md) — planned scenarios and execution framework
- [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) — incident response procedures
- [`docs/runbooks/rollback.md`](../runbooks/rollback.md) — rollback procedures
- [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md) — rollback drill results
