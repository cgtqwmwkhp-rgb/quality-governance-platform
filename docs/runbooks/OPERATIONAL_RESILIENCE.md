# Operational Resilience Runbook

**Version:** 1.0  
**Date:** 2026-01-22  
**Owner:** Platform SRE Team

## Overview

This document defines operational resilience procedures including health checks, restart safety, and recovery procedures.

## Health Check Semantics

### /healthz - Liveness Probe

**Purpose:** Indicates if the process is alive and should not be killed.

| Aspect | Specification |
|--------|---------------|
| **Response Time** | < 100ms |
| **Checks** | Process alive only |
| **Database** | NOT checked |
| **Expected Code** | 200 OK |
| **Failure Action** | Container restart |

**Response Format:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-22T19:30:00.000Z"
}
```

### /readyz - Readiness Probe

**Purpose:** Indicates if the app is ready to receive traffic.

| Aspect | Specification |
|--------|---------------|
| **Response Time** | < 5s (with DB check) |
| **Checks** | Database connectivity |
| **Timeout** | 3s for DB ping |
| **Expected Code** | 200 OK when ready |
| **Failure Action** | Remove from load balancer |

**Response Format:**
```json
{
  "status": "ready",
  "checks": {
    "database": "ok"
  },
  "timestamp": "2026-01-22T19:30:00.000Z"
}
```

**Degraded Response (503):**
```json
{
  "status": "not_ready",
  "checks": {
    "database": "connection_timeout"
  },
  "timestamp": "2026-01-22T19:30:00.000Z"
}
```

## Startup Sequence

```
┌─────────────────────────────────────────────────────────────┐
│ Container Start                                              │
├─────────────────────────────────────────────────────────────┤
│ 1. Load configuration (env vars, secrets)         ~1s       │
│ 2. Initialize logging                             ~100ms    │
│ 3. Create DB connection pool                      ~500ms    │
│ 4. Run startup healthcheck                        ~100ms    │
│ 5. Start accepting connections                    ~100ms    │
├─────────────────────────────────────────────────────────────┤
│ Total Expected Startup: 2-5 seconds                         │
│ /healthz available: immediately after step 4                │
│ /readyz available: after step 3 completes                   │
└─────────────────────────────────────────────────────────────┘
```

## Graceful Shutdown

```
┌─────────────────────────────────────────────────────────────┐
│ SIGTERM Received                                             │
├─────────────────────────────────────────────────────────────┤
│ 1. Stop accepting new connections                ~0s        │
│ 2. /readyz returns 503                           ~0s        │
│ 3. Wait for in-flight requests (30s max)         ~0-30s     │
│ 4. Close database connections                    ~500ms     │
│ 5. Exit process                                  ~0s        │
├─────────────────────────────────────────────────────────────┤
│ Total Graceful Shutdown: 0-35 seconds                       │
│ SIGKILL timeout: 60 seconds                                 │
└─────────────────────────────────────────────────────────────┘
```

## Restart Drill Procedure

### Purpose

Verify that the application restarts correctly without data loss or extended downtime.

### Pre-Drill Checklist

- [ ] Staging environment selected (never production for drills)
- [ ] Monitoring dashboards open
- [ ] Baseline metrics recorded
- [ ] Rollback procedure reviewed

### Drill Steps

1. **Record Baseline**
   ```bash
   # Record current health status
   curl -w "%{time_total}s" https://staging.example.com/healthz
   curl -w "%{time_total}s" https://staging.example.com/readyz
   ```

2. **Trigger Restart**
   ```bash
   az webapp restart \
     --name app-qgp-staging \
     --resource-group rg-qgp-staging
   ```

3. **Monitor Recovery**
   ```bash
   # Poll healthz every 5 seconds
   while true; do
     STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://staging.example.com/healthz)
     echo "$(date +%H:%M:%S) - /healthz: $STATUS"
     [ "$STATUS" = "200" ] && break
     sleep 5
   done
   ```

4. **Verify Readiness**
   ```bash
   # Confirm readyz returns 200
   curl -s https://staging.example.com/readyz | jq .
   ```

5. **Functional Verification**
   ```bash
   # Submit a test report
   curl -s -X POST https://staging.example.com/api/v1/portal/reports/ \
     -H "Content-Type: application/json" \
     -d '{"report_type":"incident","title":"Restart drill test","description":"Testing after restart","severity":"low","is_anonymous":true}'
   ```

### Expected Results

| Metric | Target | Maximum |
|--------|--------|---------|
| /healthz recovery | < 30s | 60s |
| /readyz recovery | < 45s | 90s |
| First successful request | < 60s | 120s |
| No 5xx errors after ready | 0 | 0 |

### Drill Evidence Template

```markdown
# Restart Drill Evidence

| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD |
| Environment | staging |
| Trigger | Manual restart |

## Timeline

| Time | Event |
|------|-------|
| HH:MM:SS | Restart initiated |
| HH:MM:SS | /healthz returned 200 |
| HH:MM:SS | /readyz returned 200 |
| HH:MM:SS | Drill complete |

## Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| /healthz recovery | Xs | <30s | ✅/❌ |
| /readyz recovery | Xs | <45s | ✅/❌ |
| Post-restart errors | N | 0 | ✅/❌ |

## Conclusion

[PASS/FAIL with notes]
```

## Failure Scenarios

### Scenario 1: Database Unavailable

**Symptoms:**
- /healthz returns 200
- /readyz returns 503
- API requests fail with 500

**Resolution:**
1. Check Azure PostgreSQL status
2. Verify connection string in Key Vault
3. Check network security rules
4. Restart app if connection pool corrupted

### Scenario 2: Container Crash Loop

**Symptoms:**
- Container restarts repeatedly
- /healthz never returns 200
- Deployment stuck

**Resolution:**
1. Check container logs: `az webapp log tail`
2. Verify environment variables set correctly
3. Check for missing secrets
4. Roll back to previous image if needed

### Scenario 3: Slow Startup

**Symptoms:**
- /healthz takes >60s to return 200
- Health probe timeout failures
- Container killed before ready

**Resolution:**
1. Check startup logs for slow operations
2. Verify database connection (cold start)
3. Increase health probe timeout if legitimate
4. Optimize startup sequence

### Scenario 4: Memory Pressure

**Symptoms:**
- Increasing latency
- OOM kills in logs
- Gradual degradation

**Resolution:**
1. Check memory metrics in Azure Monitor
2. Identify memory leaks in APM
3. Scale up instance size
4. Restart to clear memory

## Recovery Playbook

### Quick Recovery (< 5 min downtime)

```bash
# 1. Restart the app
az webapp restart --name app-qgp-prod --resource-group rg-qgp-prod

# 2. Monitor recovery
watch -n 5 'curl -s -o /dev/null -w "%{http_code}" https://app-qgp-prod.azurewebsites.net/healthz'

# 3. Verify readiness
curl https://app-qgp-prod.azurewebsites.net/readyz
```

### Rollback (< 15 min downtime)

```bash
# 1. List deployment history
az webapp deployment list --name app-qgp-prod --resource-group rg-qgp-prod

# 2. Rollback to previous slot
az webapp deployment slot swap \
  --name app-qgp-prod \
  --resource-group rg-qgp-prod \
  --slot staging \
  --target-slot production

# 3. Verify
curl https://app-qgp-prod.azurewebsites.net/healthz
```

### Full Recovery (> 15 min)

1. Engage incident response team
2. Create incident ticket
3. Follow escalation matrix
4. Document timeline
5. Post-mortem within 48 hours

## Maintenance Windows

### Scheduled Maintenance

| Type | Frequency | Duration | Impact |
|------|-----------|----------|--------|
| Patch updates | Weekly | 5-10 min | Minimal |
| Version upgrades | Monthly | 15-30 min | Brief outage |
| Infrastructure | Quarterly | 1-2 hours | Planned outage |

### Maintenance Notification

- 72 hours notice for planned outages
- Status page update before/during/after
- Stakeholder email for major changes

## References

- [Azure App Service Health Checks](https://docs.microsoft.com/azure/app-service/monitor-instances-health-check)
- [Kubernetes Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [SRE Book - Handling Overload](https://sre.google/sre-book/handling-overload/)
