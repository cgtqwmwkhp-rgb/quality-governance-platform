# Resilience Patterns Catalog (D05)

**Owner:** Platform Engineering
**Last Updated:** 2026-04-04
**Review Cycle:** Quarterly (aligned with chaos testing cadence)
**Classification:** Internal (C2)

---

## Purpose

Comprehensive inventory of all resilience patterns implemented in the Quality Governance Platform (QGP), with code references, test evidence, and operational procedures. This catalog serves as:

- A reference for developers adding new integrations or services
- An audit artifact demonstrating resilience controls (D05)
- A training resource for on-call engineers
- Input for chaos testing planning

---

## Pattern Inventory

### 1. Circuit Breaker

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/infrastructure/resilience/circuit_breaker.py`](../../src/infrastructure/resilience/circuit_breaker.py) |
| **Class** | `CircuitBreaker` (lines 39–172) |
| **Protects** | External service calls (Azure AD, SMTP relay, any downstream dependency) |

**State machine:** `CLOSED` → `OPEN` → `HALF_OPEN` → `CLOSED`

```
CLOSED ──(failure_threshold reached)──► OPEN
                                          │
                              (recovery_timeout elapsed)
                                          │
                                          ▼
                                      HALF_OPEN
                                       │    │
                          (probe succeeds)  (probe fails)
                               │               │
                               ▼               ▼
                            CLOSED           OPEN
```

**Configuration defaults:**

| Parameter | Value | Source |
|-----------|-------|--------|
| `failure_threshold` | 5 consecutive failures | `circuit_breaker.py` line 46 |
| `recovery_timeout` | 60.0 seconds | `circuit_breaker.py` line 47 |
| `half_open_max_calls` | 1 probe call | `circuit_breaker.py` line 48 |

**Behaviour:**

- When **CLOSED**: calls pass through normally; failures increment the counter.
- When **OPEN**: calls are rejected immediately with `CircuitBreakerOpenError` — no socket-level wait (fail-fast).
- When **HALF_OPEN**: a single probe call is allowed through (`half_open_max_calls=1`); success resets to CLOSED, failure re-opens the circuit.
- The state property auto-transitions from OPEN to HALF_OPEN once `recovery_timeout` elapses (lines 67–71), without requiring an explicit timer.

**Global registry:**

All circuit breaker instances self-register in `_circuit_registry` (line 64), enabling global introspection via `get_all_circuits()`. The `/readyz` health endpoint iterates this registry to include circuit breaker health in every readiness response (see [Pattern 2](#2-health-check-cascade)).

**Monitoring:**

State transitions emit Azure Monitor metrics via `_emit_transition_metric()` (lines 131–151):

| Metric | Description |
|--------|-------------|
| `circuit_breaker.<name>.transition` | Counter incremented on each state change |
| `circuit_breaker.<name>.state` | Gauge: 0=closed, 1=half_open, 2=open |
| `circuit_breaker.<name>.total_failures` | Cumulative failure count |

Transition history is capped at 100 entries (line 127) and exposed via `get_health()` (lines 164–172).

**Manual reset:** `await circuit.reset()` forces a circuit back to CLOSED (line 153), useful during incident recovery.

**Test evidence:** Chaos test #1 — circuit breaker tripped after exactly 5 failures, rejected all subsequent calls during the OPEN window, and recovered via HALF_OPEN probe after 60 seconds. See [`docs/evidence/chaos-testing-results.md` § Test 1](../evidence/chaos-testing-results.md).

---

### 2. Health Check Cascade

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/api/routes/health.py`](../../src/api/routes/health.py) |
| **Endpoints** | `/healthz`, `/readyz`, `/diagnostics`, `/metrics/resources` |

**Endpoint hierarchy:**

| Endpoint | Purpose | I/O | Timeout | Used by |
|----------|---------|-----|---------|---------|
| `GET /healthz` | Liveness probe | None (no downstream calls) | — | Azure App Service health probe, Kubernetes liveness |
| `GET /readyz` | Readiness probe | DB `SELECT 1`, Redis `PING`, PAMS reflection | DB: 3 s, Redis: 2 s | Load balancer, Kubernetes readiness, deployment slot validation |
| `GET /diagnostics` | Operational visibility | Alembic (subprocess, 5 s timeout) | 5 s | On-call engineers, dashboards |
| `GET /metrics/resources` | Resource utilization | psutil (local) | — | Cost monitoring, autoscaling decisions |

**Failure semantics:**

| Component | Failure impact on `/readyz` |
|-----------|---------------------------|
| Database | **Fatal** — returns HTTP 503, `status: "not_ready"` (lines 50–54) |
| Redis | **Non-fatal** — returns HTTP 200, `redis: "degraded"` (lines 67–69) |
| PAMS | **Non-fatal** — returns HTTP 200, `pams: "error"` or `"not_configured"` (lines 71–81) |
| Circuit breakers | Included in response payload for visibility; does not affect status code (lines 83–90) |

**Design rationale:** Database is the single hard dependency. Redis and PAMS are "nice to have" — their unavailability degrades functionality but does not prevent the application from serving requests. This distinction prevents unnecessary restarts during partial outages.

**Resource metrics in `/readyz`:** Memory (RSS) and CPU utilization are included (lines 101–102) to provide a complete picture of instance health alongside dependency checks.

**Test evidence:** Chaos test #4 — `/healthz` maintained p99 of 8 ms and `/readyz` maintained p99 of 42 ms under sustained 100-user load for 15 minutes. See [`docs/evidence/chaos-testing-results.md` § Test 4](../evidence/chaos-testing-results.md).

---

### 3. Idempotency with Graceful Degradation

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/api/middleware/idempotency.py`](../../src/api/middleware/idempotency.py) |
| **Class** | `IdempotencyMiddleware` (lines 80–245) |
| **Scope** | All `POST`, `PUT`, `PATCH` requests carrying an `Idempotency-Key` header |

**Normal flow (Redis available):**

1. Client sends mutating request with `Idempotency-Key: <uuid>` header.
2. Middleware computes SHA-256 hash of the request body (line 69).
3. Checks Redis for key `idem:<uuid>`:
   - **Cache hit, hash matches** → returns cached response (replay).
   - **Cache hit, hash differs** → returns HTTP 409 `IDEMPOTENCY_CONFLICT` (lines 129–144).
   - **Cache miss** → executes request, caches response with 24-hour TTL (line 222).
4. Requests without the header pass through unmodified (line 100).

**Degraded flow (Redis unavailable):**

When `_get_redis()` returns `None` (connection failure or `redis_url` not set), the middleware **fails open**: it logs a debug message and forwards the request to the handler without idempotency protection (lines 104–107).

**Trade-off:** Availability is prioritized over exactly-once semantics. When Redis is down, duplicate requests may execute twice. Database unique constraints and domain validation provide a safety net against data corruption. This trade-off is documented and accepted.

**Redis connection configuration:**

| Parameter | Value | Source |
|-----------|-------|--------|
| `max_connections` | 20 | `idempotency.py` line 44 |
| `socket_connect_timeout` | 5 s | `idempotency.py` line 45 |
| `socket_timeout` | 5 s | `idempotency.py` line 46 |
| `retry_on_timeout` | True | `idempotency.py` line 47 |
| `health_check_interval` | 30 s | `idempotency.py` line 50 |
| Response cache TTL | 86,400 s (24 hours) | `idempotency.py` line 222 |

**Test evidence:** Chaos test #2 — when Redis was stopped, the middleware logged the degradation and all requests continued to be served. No user-visible errors during the 10-minute outage. See [`docs/evidence/chaos-testing-results.md` § Test 2](../evidence/chaos-testing-results.md).

---

### 4. Retry with Exponential Backoff

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/infrastructure/resilience/circuit_breaker.py`](../../src/infrastructure/resilience/circuit_breaker.py) lines 185–262 |
| **Function** | `retry_with_backoff` decorator |

**Configuration defaults:**

| Parameter | Value |
|-----------|-------|
| `max_retries` | 3 |
| `base_delay` | 0.5 s |
| `max_delay` | 30.0 s |
| `retryable_exceptions` | `ConnectionError`, `TimeoutError`, `OSError` |

**Backoff formula:** `delay = min(base_delay × 2^attempt, max_delay) + uniform(0, delay × 0.5)`

The jitter component (up to 50% of the computed delay) decorrelates concurrent retry attempts to prevent thundering herd / retry storms.

**Supports both async and sync functions** — the decorator inspects `asyncio.iscoroutinefunction(func)` (line 209) and wraps accordingly.

**Celery global retries:**

In addition to the `retry_with_backoff` decorator, Celery tasks have a global retry policy configured in [`src/infrastructure/tasks/celery_app.py`](../../src/infrastructure/tasks/celery_app.py) (lines 74–78):

| Parameter | Value |
|-----------|-------|
| `task_autoretry_for` | `ConnectionError`, `TimeoutError`, `IOError` |
| `task_retry_backoff` | True (exponential) |
| `task_retry_backoff_max` | 600 s |
| `task_max_retries` | 3 |
| `task_retry_jitter` | True |

**Per-task retry overrides:**

| Task | `max_retries` | `default_retry_delay` | Source |
|------|---------------|-----------------------|--------|
| `send_email` | 3 | 60 s | `email_tasks.py` line 28 |
| `send_push_notification` | 3 | 30 s | `notification_tasks.py` line 42 |
| `send_sms` | 3 | 30 s | `sms_tasks.py` line 13 |
| `run_data_retention` | 3 | 300 s (explicit countdown) | `cleanup_tasks.py` line 24 |
| `process_external_audit_import_job` | 2 | 10 s (explicit countdown) | `external_audit_import_tasks.py` line 38 |
| `sync_pams_checklists` | 2 | (global backoff) | `pams_sync_tasks.py` line 380 |
| `generate_report` | 1 | (global backoff) | `report_tasks.py` line 13 |
| `check_competency_expiry` | 3 | 300 s (explicit countdown) | `competency_tasks.py` line 15 |

**Test evidence:** Chaos test #5 — with 50% packet loss, ~85% of requests succeeded within the retry budget. Log entries confirmed the `base_delay × 2^attempt + jitter` formula. No retry storms observed. See [`docs/evidence/chaos-testing-results.md` § Test 5](../evidence/chaos-testing-results.md).

---

### 5. Timeout Enforcement

Timeouts are configured at multiple layers to prevent indefinite waits:

| Layer | Timeout | Source |
|-------|---------|--------|
| **PostgreSQL statement timeout** | 30 s | `database.py` line 46 (`statement_timeout: "30000"`) |
| **SQLAlchemy pool checkout timeout** | 30 s | `database.py` line 44 (`pool_timeout: 30`) |
| **SQLAlchemy connection pool recycle** | 1,800 s (30 min) | `database.py` line 43 (`pool_recycle: 1800`) |
| **Pool pre-ping** | Enabled | `database.py` line 40 (`pool_pre_ping: True`) |
| **Readiness probe DB check** | 3 s | `health.py` line 48 (`asyncio.wait_for(..., timeout=3.0)`) |
| **Readiness probe Redis check** | 2 s (connect) + 2 s (ping) | `health.py` lines 62–63 |
| **Idempotency Redis socket timeout** | 5 s | `idempotency.py` line 46 |
| **Idempotency Redis connect timeout** | 5 s | `idempotency.py` line 45 |
| **Celery task soft time limit** | 300 s (5 min) | `celery_app.py` line 64 |
| **Celery task hard time limit** | 600 s (10 min) | `celery_app.py` line 65 |
| **Report generation soft time limit** | 600 s (10 min) | `report_tasks.py` line 15 |
| **PAMS sync soft time limit** | 300 s (5 min) | `pams_sync_tasks.py` line 381 |
| **Diagnostics Alembic subprocess** | 5 s | `health.py` line 119 |

**Design principle:** Every outbound call and every long-running operation has an explicit timeout. No unbounded waits exist in the system.

**Test evidence:** Chaos test #3 — requests exceeding the 30 s pool timeout received HTTP 503. No leaked connections or partial writes observed. See [`docs/evidence/chaos-testing-results.md` § Test 3](../evidence/chaos-testing-results.md).

---

### 6. Graceful Degradation

The platform is designed to remain functional when non-critical subsystems fail:

#### 6a. Cache Layer Fallback

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/infrastructure/cache/redis_cache.py`](../../src/infrastructure/cache/redis_cache.py) |
| **Classes** | `RedisCache` (lines 130–268), `InMemoryCache` (lines 50–127) |

`RedisCache` wraps every Redis operation in try/except blocks. On connection failure, it transparently delegates to an embedded `InMemoryCache` instance (LRU, max 1,000 items). Operations that fail mid-stream also fall back to the in-memory cache.

**Impact when degraded:** Cache hit rate drops (~78% → ~12% per chaos test observations) because the in-memory cache is per-instance and cold. No data loss or incorrect behavior.

#### 6b. PAMS Integration (Optional)

The `/readyz` endpoint treats PAMS as a non-critical dependency (lines 71–81). When PAMS is unavailable, the platform continues operating without external checklist data. PAMS status is reported as `"not_configured"`, `"error"`, or `"no_tables"` — none of which trigger a 503.

#### 6c. Rate Limiter Fallback

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/infrastructure/middleware/rate_limiter.py`](../../src/infrastructure/middleware/rate_limiter.py) |

The rate limiter supports both Redis-backed (distributed) and in-memory (per-instance) modes. When Redis is unavailable, rate limiting falls back to the in-memory sliding window — per-instance rather than per-cluster, but still protective.

#### 6d. Error Handler — User-Safe Responses

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/api/middleware/error_handler.py`](../../src/api/middleware/error_handler.py) |
| **Function** | `register_exception_handlers()` (lines 107–176) |

Four exception handlers convert internal errors into a consistent, user-safe JSON envelope:

| Exception type | HTTP status | Error code |
|----------------|-------------|------------|
| `DomainError` subclasses | Per `exc.http_status` | Per `exc.code` |
| `StarletteHTTPException` | Per `exc.status_code` | Mapped from status |
| `RequestValidationError` | 422 | `VALIDATION_ERROR` |
| Unhandled `Exception` | 500 | `INTERNAL_ERROR` |

**Key behaviors:**

- Internal stack traces and implementation details are **never** leaked to clients (line 174 returns a generic message).
- Every error response includes a `request_id` for correlation with server-side logs.
- Unhandled exceptions trigger `record_5xx_error()` (line 171) to increment the Azure Monitor 5xx counter.
- CORS headers are injected directly into error responses as a safety net (lines 87–104), because Starlette's `CORSMiddleware` can miss errors that propagate through `BaseHTTPMiddleware` layers.

---

### 7. Dead Letter Queue (DLQ)

| Attribute | Detail |
|-----------|--------|
| **DLQ handler** | [`src/infrastructure/tasks/dlq.py`](../../src/infrastructure/tasks/dlq.py) |
| **DLQ replay** | [`src/infrastructure/tasks/dlq_replay.py`](../../src/infrastructure/tasks/dlq_replay.py) |

**Pattern:** When a Celery task exhausts all retries and permanently fails, the `task_failure` signal handler (line 80) persists a `FailedTask` record to the database with task name, ID, exception, and arguments.

**Alerting thresholds:**

| Threshold | Level | Action |
|-----------|-------|--------|
| ≥ 10 entries | WARNING | `dlq.alert` metric with `severity: warning` |
| ≥ 50 entries | CRITICAL | `dlq.alert` metric with `severity: critical` |

**Automated replay:** The `replay_failed_tasks` Celery task (scheduled via beat) re-dispatches un-retried DLQ entries. Each entry is retried at most once; after dispatch it is marked `retried=True` with a `retried_at` timestamp.

**Safety:** Replay failures are caught per-entry with `session.rollback()` (line 82 of `dlq_replay.py`), preventing one bad entry from blocking the entire replay batch.

---

### 8. Database Connection Pool Management

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/infrastructure/database.py`](../../src/infrastructure/database.py) |

**Production pool configuration (PostgreSQL):**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `pool_size` | 10 | Steady-state connection count |
| `max_overflow` | 20 | Burst capacity (total max: 30) |
| `pool_recycle` | 1,800 s | Recycle connections to avoid stale TCP |
| `pool_timeout` | 30 s | Max wait for a connection from the pool |
| `pool_pre_ping` | True | Validate connections before use (detects server restarts) |

**Session management:** The `get_db()` dependency (lines 114–124) uses `try/except/finally` to guarantee:
- `commit()` on success
- `rollback()` on any exception
- `close()` always

**Pool usage monitoring:** Checkout/checkin events are tracked via SQLAlchemy pool event listeners (lines 89–104). The `db.pool_usage_percent` metric is emitted periodically (line 111) and was validated during chaos test #3 to reach 100% under saturation.

**Test evidence:** Chaos test #3 — with a constrained pool (5 connections, 50 concurrent users), requests exceeding capacity received 503 after the 30 s timeout. No connection leaks or data corruption. See [`docs/evidence/chaos-testing-results.md` § Test 3](../evidence/chaos-testing-results.md).

---

### 9. Deployment Safety

| Attribute | Detail |
|-----------|--------|
| **Deploy workflow** | [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) |
| **Rollback workflow** | [`.github/workflows/rollback-production.yml`](../../.github/workflows/rollback-production.yml) |
| **Rollback runbook** | [`docs/runbooks/rollback.md`](../runbooks/rollback.md) |
| **Rollback drills** | [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md) |

#### Zero-Downtime Deployment

Production deploys use Azure App Service deployment slots (staging → production slot swap). The staging slot receives the new image, passes health check validation (`/healthz`, `/readyz`), and then a slot swap atomically routes traffic — achieving near-zero downtime (~8 s observed in drills).

#### Deploy Freeze Windows

Production deploys are **frozen from Friday 16:00 UTC through Monday 09:00 UTC** (`deploy-production.yml` line 27). The `force_deploy` input allows authorized overrides with justification.

#### Rollback Procedures

| Method | RTO | Procedure |
|--------|-----|-----------|
| **Slot swap reversal** | ~8 s | Swap production slot back to previous image |
| **Image pin rollback** | ~30 s + health check | `rollback-production.yml` — specify ACR image SHA, workflow deploys previous image and validates health |

The rollback workflow includes:
1. Azure login and ACR authentication
2. Image existence verification in ACR
3. Container image pin (`az webapp config container set`)
4. Health check polling (up to 20 attempts × 10 s intervals)
5. Summary output for audit trail

#### Pre-Deployment Checks

The production deploy workflow enforces:
- Staging success verification (for auto-trigger via `workflow_run`)
- Manual staging verification confirmation (for `workflow_dispatch`)
- Deploy freeze window enforcement
- Concurrency control (`cancel-in-progress: false` prevents concurrent deploys)

---

### 10. Data Protection Patterns

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/domain/models/base.py`](../../src/domain/models/base.py) |

#### 10a. Soft Delete (`SoftDeleteMixin`, lines 87–100)

Records are never physically deleted. Instead, `deleted_at` is set to the current timestamp. The `is_deleted` property (line 98) provides a convenience check. All queries should filter on `deleted_at IS NULL` to exclude soft-deleted records.

**Resilience benefit:** Accidental deletions are recoverable without database restore. Supports regulatory data retention requirements.

#### 10b. Audit Trail (`AuditTrailMixin`, lines 103–107)

Tracks `created_by_id` and `updated_by_id` on every auditable entity. Combined with `TimestampMixin` (lines 57–73), this provides a complete record of who created or last modified each record and when.

#### 10c. Timestamps (`TimestampMixin`, lines 57–73)

All domain models inherit `created_at` and `updated_at` with:
- Python-side defaults (`datetime.now(timezone.utc)`)
- Server-side defaults (`func.now()`) for database-level safety
- Automatic `onupdate` for `updated_at`
- `created_at` is indexed for efficient time-range queries

#### 10d. Data Classification (`DataClassification`, lines 115–142)

Models declare their data classification tier (C1–C4) via `__data_classification__`. The classification drives handling requirements:

| Tier | Handling |
|------|----------|
| C1 Public | No special handling |
| C2 Internal | Internal use only |
| C3 Confidential | Access limited, encrypted at rest |
| C4 Restricted | PII — encrypted, pseudonymised on erasure, audit-logged |

---

### 11. Celery Task Safety

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/infrastructure/tasks/celery_app.py`](../../src/infrastructure/tasks/celery_app.py) |

**Global safety settings:**

| Setting | Value | Purpose |
|---------|-------|---------|
| `task_acks_late` | True | Acknowledge after execution — prevents message loss on worker crash |
| `worker_prefetch_multiplier` | 1 | Fetch one task at a time — prevents overloading |
| `task_track_started` | True | Track task start time for monitoring |
| `task_soft_time_limit` | 300 s | Raise `SoftTimeLimitExceeded` — allows cleanup |
| `task_time_limit` | 600 s | Hard kill — prevents infinite loops |

**Queue isolation:** Tasks are routed to dedicated queues (`default`, `email`, `notifications`, `reports`, `cleanup`) to prevent slow tasks from blocking critical ones.

---

## Chaos Testing Evidence

All resilience patterns have been validated through structured chaos testing conducted on 2026-04-02 in the staging environment.

| Test | Scenario | Pattern validated | Result |
|------|----------|-------------------|--------|
| 1 | External service failure (NSG deny) | Circuit breaker | **PASS** |
| 2 | Redis unavailability (container stop) | Idempotency fallback, cache fallback, health cascade | **PASS** |
| 3 | DB connection pool exhaustion (reduced pool + Locust) | Pool timeout, session rollback, pool monitoring | **PASS** |
| 4 | Health check under load (100 users, 15 min) | Health probe responsiveness | **PASS** |
| 5 | Transient failures (50% packet loss) | Retry with exponential backoff | **PASS** |

**Overall result:** All resilience mechanisms performed as designed. No data loss, no cascading failures, graceful degradation confirmed.

Full details: [`docs/evidence/chaos-testing-results.md`](../evidence/chaos-testing-results.md)

**Planned tests (not yet executed):**
- Azure Blob storage timeout (deferred due to staging configuration)
- Database point-in-time restore (PITR) — planned Q2 2026

---

## Rollback Drill History

| # | Date | Type | Duration | Result |
|---|------|------|----------|--------|
| 1 | 2026-03-15 | Production slot swap rollback | 8 seconds | **Successful** |
| 2 | 2026-03-20 | Audit module rollback drill | ~2 minutes | **Successful** |

**Database PITR drill:** Planned for Q2 2026 in staging. Not yet conducted. Target: validate RTO/RPO actuals against current targets (RTO: 8 s slot swap, RPO: 0).

**Drill cadence:** Quarterly for slot swap rollbacks; semi-annually for DB PITR.

Full details: [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md)

---

## Recovery Procedures

Cross-reference runbooks for each failure mode:

| Failure mode | Recovery procedure | Runbook |
|-------------|-------------------|---------|
| Application regression | Slot swap reversal or image pin rollback | [`docs/runbooks/rollback.md`](../runbooks/rollback.md) |
| Database corruption | Point-in-time restore (PITR) | [`docs/ops/DISASTER_RECOVERY_RUNBOOK.md`](../ops/DISASTER_RECOVERY_RUNBOOK.md) |
| Cascading external failure | Circuit breaker auto-recovery (60 s) or manual reset | [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) |
| Redis total failure | Automatic failover to in-memory cache/idempotency bypass | Self-healing; monitor via `/readyz` |
| DLQ backlog | Review DLQ entries, fix root cause, trigger replay | [`docs/runbooks/support-escalation.md`](../runbooks/support-escalation.md) |
| Incident response | Structured escalation workflow | [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) |

---

## Pattern Coverage Matrix

| # | Pattern | Components protected | Chaos tested | Monitored | Documented |
|---|---------|---------------------|--------------|-----------|------------|
| 1 | Circuit breaker | External services (Azure AD, SMTP) | Yes (Test 1) | Yes (Azure Monitor metrics) | Yes |
| 2 | Health check cascade | All dependencies (DB, Redis, PAMS) | Yes (Test 4) | Yes (probe endpoints) | Yes |
| 3 | Idempotency + degradation | Mutating API requests | Yes (Test 2) | Yes (Redis health in `/readyz`) | Yes |
| 4 | Retry with backoff | HTTP decorator + all Celery tasks | Yes (Test 5) | Yes (retry log entries) | Yes |
| 5 | Timeout enforcement | DB, Redis, Celery, health probes | Yes (Test 3) | Yes (pool metrics, probe latency) | Yes |
| 6 | Graceful degradation | Cache, PAMS, rate limiter, error handler | Yes (Test 2) | Yes (degraded status in `/readyz`) | Yes |
| 7 | Dead letter queue | All Celery tasks (post-retry) | Implicit (via retries) | Yes (DLQ depth metrics + alerts) | Yes |
| 8 | DB connection pool mgmt | All database operations | Yes (Test 3) | Yes (`db.pool_usage_percent`) | Yes |
| 9 | Deployment safety | Production releases | Yes (rollback drills) | Yes (health check validation) | Yes |
| 10 | Data protection | All domain entities | N/A (design pattern) | Yes (audit trail) | Yes |
| 11 | Celery task safety | All background tasks | Implicit (via retries) | Yes (task tracking) | Yes |

### Gaps and Planned Improvements

| Gap | Plan | Target |
|-----|------|--------|
| Azure Blob storage timeout not chaos-tested | Execute Scenario 3 from chaos testing plan | Q2 2026 |
| Database PITR not drilled | Conduct PITR drill in staging | Q2 2026 |
| Circuit breaker alerting | Add Azure Monitor alert for OPEN > 5 min | Q2 2026 |
| Automated chaos injection | Evaluate LitmusChaos or Azure Chaos Studio | Q3 2026 |

---

## Related Documents

- [`docs/evidence/chaos-testing-results.md`](../evidence/chaos-testing-results.md) — chaos test execution results
- [`docs/evidence/chaos-testing-plan.md`](../evidence/chaos-testing-plan.md) — planned scenarios and framework
- [`docs/runbooks/rollback.md`](../runbooks/rollback.md) — rollback procedures
- [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md) — drill history and schedule
- [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) — incident response
- [`docs/ops/DISASTER_RECOVERY_RUNBOOK.md`](../ops/DISASTER_RECOVERY_RUNBOOK.md) — disaster recovery
- [`docs/ops/kql-queries.md`](../ops/kql-queries.md) — KQL queries for monitoring
- [`docs/architecture/module-boundaries.md`](module-boundaries.md) — module boundary definitions
