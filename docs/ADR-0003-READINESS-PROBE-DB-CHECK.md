# ADR-0003: Readiness Probe Database Check

**Status**: Accepted  
**Date**: 2026-01-05  
**Decision Makers**: Platform Team  
**Affected Components**: `/readyz` endpoint, health checks, container orchestration

---

## Context

The Quality Governance Platform implements two health endpoints:
1. **`/healthz`** (liveness probe): Indicates if the application process is alive
2. **`/readyz`** (readiness probe): Indicates if the application is ready to accept traffic

The `/readyz` endpoint currently exists but does not check database connectivity. We need to decide whether to add a database ping check to `/readyz` or keep it as a simple application-level check.

---

## Decision

**We will implement a database connectivity check in the `/readyz` endpoint.**

The `/readyz` endpoint will:
1. Return 200 OK with `{"status": "ready", "database": "connected"}` if the database is reachable
2. Return 503 Service Unavailable with `{"status": "not_ready", "database": "disconnected", "error": "<details>"}` if the database is unreachable

---

## Rationale

### Why Add Database Check

1. **Prevent Cascading Failures**:
   - Without a DB check, the load balancer may route traffic to an instance that cannot serve requests
   - This causes 500 errors for users and increases error rates
   - Database connection issues are the most common cause of application unavailability

2. **Container Orchestration Best Practice**:
   - Kubernetes and Azure App Service use readiness probes to remove unhealthy instances from load balancer rotation
   - A readiness probe should check all critical dependencies, not just process health
   - This prevents "zombie" instances that are alive but cannot serve traffic

3. **Graceful Degradation**:
   - During database maintenance or failover, instances can be marked as not ready
   - Traffic is automatically routed to healthy instances
   - No manual intervention required

4. **Operational Visibility**:
   - Readiness probe failures are logged and alerted
   - Operators can quickly identify database connectivity issues
   - Reduces mean time to detection (MTTD)

### Why Not Just Use Liveness Probe

1. **Liveness vs Readiness Semantics**:
   - **Liveness**: "Is the process alive?" → If no, restart the container
   - **Readiness**: "Can the process serve traffic?" → If no, remove from load balancer
   
2. **Database Connection Issues Are Often Transient**:
   - Restarting the container (liveness failure) doesn't fix database issues
   - Removing from load balancer (readiness failure) allows time for recovery
   - Prevents unnecessary container restarts

3. **Separation of Concerns**:
   - Liveness checks application health (process, memory leaks, deadlocks)
   - Readiness checks service availability (database, external APIs, caches)

---

## Implementation

### Endpoint Specification

**URL**: `GET /readyz`

**Success Response** (200 OK):
```json
{
  "status": "ready",
  "database": "connected",
  "request_id": "<uuid>"
}
```

**Failure Response** (503 Service Unavailable):
```json
{
  "status": "not_ready",
  "database": "disconnected",
  "error": "connection timeout",
  "request_id": "<uuid>"
}
```

### Implementation Code

**File**: `src/main.py`

```python
from fastapi import FastAPI, status
from sqlalchemy import text
from src.core.database import get_db

@app.get("/readyz", status_code=status.HTTP_200_OK)
async def readiness_check():
    """
    Readiness probe: Check if application is ready to accept traffic.
    Checks database connectivity.
    """
    request_id = str(uuid.uuid4())
    
    try:
        # Ping database with a simple query
        async with get_db() as db:
            await db.execute(text("SELECT 1"))
        
        return {
            "status": "ready",
            "database": "connected",
            "request_id": request_id
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", extra={"request_id": request_id})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": str(e),
                "request_id": request_id
            }
        )
```

### Container Health Check Configuration

**Dockerfile**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1
```

**docker-compose.yml**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/readyz"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

**Azure App Service**:
- Health check path: `/readyz`
- Interval: 30 seconds
- Timeout: 10 seconds
- Unhealthy threshold: 3 consecutive failures

---

## Consequences

### Positive

1. **Improved Reliability**:
   - Instances with database connection issues are automatically removed from rotation
   - Users experience fewer 500 errors
   - Faster recovery from transient database issues

2. **Better Observability**:
   - Readiness probe failures are logged and alerted
   - Clear signal for database connectivity issues
   - Easier troubleshooting

3. **Operational Best Practice**:
   - Aligns with Kubernetes and cloud platform best practices
   - Enables graceful degradation during maintenance
   - Supports zero-downtime deployments

### Negative

1. **Slight Performance Overhead**:
   - Each readiness check executes a database query (`SELECT 1`)
   - Mitigation: Use connection pooling, check interval is 30s (not per-request)

2. **Potential for False Negatives**:
   - Transient network issues may cause readiness failures
   - Mitigation: Set retries to 3, timeout to 10s

3. **Complexity**:
   - Readiness probe is more complex than a simple HTTP check
   - Mitigation: Clear documentation and error messages

---

## Alternatives Considered

### Alternative 1: No Database Check (Status Quo)

**Pros**:
- Simpler implementation
- No database query overhead

**Cons**:
- Instances with database connection issues remain in rotation
- Users experience 500 errors
- Difficult to identify database connectivity issues

**Decision**: Rejected due to poor user experience and operational visibility

### Alternative 2: Separate Database Health Endpoint

**Pros**:
- Separation of concerns (readiness vs database health)
- Can be used for monitoring without affecting load balancer

**Cons**:
- Requires two health checks (readiness + database)
- More complex configuration
- Doesn't solve the core problem (unhealthy instances in rotation)

**Decision**: Rejected due to added complexity without significant benefit

### Alternative 3: Readiness Check with Timeout and Circuit Breaker

**Pros**:
- Prevents cascading failures from slow database queries
- Automatically opens circuit after repeated failures

**Cons**:
- Significantly more complex implementation
- Overkill for readiness probe (timeout is sufficient)

**Decision**: Rejected due to over-engineering (can be added later if needed)

---

## Implementation Plan

### Phase 1: Implement `/readyz` with Database Check
- [ ] Add database ping query to `/readyz` endpoint
- [ ] Return 503 on database connection failure
- [ ] Add request_id to response
- [ ] Add error logging

### Phase 2: Update Health Check Configuration
- [ ] Update docker-compose.yml to use `/readyz`
- [ ] Update Azure App Service health check path
- [ ] Update deployment runbook

### Phase 3: Testing
- [ ] Unit test for `/readyz` endpoint
- [ ] Integration test with database connection failure simulation
- [ ] Verify load balancer behavior (remove unhealthy instances)

### Phase 4: Documentation
- [ ] Update DEPLOYMENT_RUNBOOK.md
- [ ] Update AZURE_STAGING_BLUEPRINT.md
- [ ] Add troubleshooting guide for readiness failures

---

## Monitoring and Alerting

### Metrics to Track

1. **Readiness Probe Success Rate**:
   - Target: > 99.9%
   - Alert: < 95% over 5 minutes

2. **Readiness Probe Latency**:
   - Target: < 100ms (P95)
   - Alert: > 500ms (P95) over 5 minutes

3. **Instances Not Ready**:
   - Target: 0
   - Alert: > 1 instance for > 5 minutes

### Application Insights Query

```kusto
requests
| where name == "GET /readyz"
| where resultCode != "200"
| summarize count() by bin(timestamp, 5m), resultCode
```

---

## References

- [Kubernetes Liveness and Readiness Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Azure App Service Health Check](https://docs.microsoft.com/en-us/azure/app-service/monitor-instances-health-check)
- [12-Factor App: Health Checks](https://12factor.net/)

---

## Approval

**Proposed By**: Platform Team  
**Reviewed By**: [Pending]  
**Approved By**: [Pending]  
**Date**: 2026-01-05

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-05 | Platform Team | Initial decision |
