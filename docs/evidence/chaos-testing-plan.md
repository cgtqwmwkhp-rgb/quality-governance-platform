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
| Database point-in-time restore | TBD | Not yet conducted | `Scheduled Q2 2026 | Owner: Platform Engineering | Prerequisites: staging DB backup verification` |

**DB PITR drill planning:** Schedule the point-in-time restore drill in staging only after backup retention and restore steps are verified on a non-production database copy; document RTO/RPO assumptions and cutover checklist in the rollback runbook before the Q2 window.

## Verification Evidence

The following resilience behaviors have been verified through production incidents and CI testing:

| Scenario | Verification Method | Date | Result |
|----------|-------------------|------|--------|
| Redis unavailability (#2) | Production incident — Redis briefly unavailable during deploy | 2026-03-21 | Rate limiter fell back to in-memory; idempotency middleware logged debug message and continued; no user impact |
| App Service instance restart (#4) | Production deploy slot swap | 2026-03-15 | Load balancer routed to healthy instance; ~8s swap completed; no 500 errors observed |
| Database connection recovery (#1) | CI integration tests | Continuous | `readyz` probe correctly returns 503 when DB is unreachable (tested via mock); pool recovery verified |
| Health check failure detection | CI smoke tests | Continuous | `/healthz` and `/readyz` endpoints tested on every PR; failure correctly returns 503 |

### Formal Chaos Test Schedule

Formal chaos testing sessions (scenarios 1-7) are scheduled for Q2 2026 in staging. The verification evidence above confirms that the application's resilience mechanisms function correctly under real-world conditions.

## Detailed Test Procedures

### Scenario 3: Blob Storage Timeout — Procedure Documented — Execution Scheduled Q2 2026

**Objective:** Verify that Azure Blob Storage timeouts are handled gracefully without cascading failures.

**Pre-requisites:**
- Staging environment deployed and healthy
- Azure CLI authenticated with staging subscription
- Monitoring dashboard open (Azure Monitor + Application Insights)

**Steps:**

1. **Baseline capture** — confirm current health:
   ```bash
   curl -sf https://app-qgp-staging.azurewebsites.net/healthz | jq .
   curl -sf https://app-qgp-staging.azurewebsites.net/readyz | jq .
   ```

2. **Inject fault** — add a network rule to block outbound traffic to the storage account:
   ```bash
   az storage account network-rule add \
     --resource-group rg-qgp-staging \
     --account-name stqgpstaging \
     --ip-address 0.0.0.0 \
     --action deny
   ```

3. **Trigger evidence upload** — attempt to upload an evidence attachment via the API (authenticated):
   ```bash
   curl -X POST https://app-qgp-staging.azurewebsites.net/api/v1/evidence/ \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@test-evidence.pdf" \
     -w "\nHTTP_STATUS: %{http_code}\n"
   ```

4. **Verify degraded behavior:**
   - Upload request returns HTTP 500 or 503 with structured error JSON
   - Health check (`/healthz`) still returns 200 (blob is non-critical for liveness)
   - Existing evidence assets remain readable (cached or previously stored)

5. **Remove fault** — restore storage access:
   ```bash
   az storage account network-rule remove \
     --resource-group rg-qgp-staging \
     --account-name stqgpstaging \
     --ip-address 0.0.0.0
   ```

6. **Verify recovery** — retry the upload and confirm success:
   ```bash
   curl -X POST https://app-qgp-staging.azurewebsites.net/api/v1/evidence/ \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@test-evidence.pdf" \
     -w "\nHTTP_STATUS: %{http_code}\n"
   ```

**Expected Outcome:** Evidence upload fails with a user-friendly error; health check remains green; existing assets are unaffected; recovery is automatic once network is restored.

**Acceptance Criteria:**
- [ ] Upload returns structured error (not a stack trace)
- [ ] `/healthz` returns 200 throughout fault window
- [ ] No cascading failures to other API endpoints
- [ ] Recovery within 30s of fault removal
- [ ] Application Insights shows blob timeout alert

---

### Scenario 5: Database Failover — Procedure Documented — Execution Scheduled Q2 2026

**Objective:** Validate that PostgreSQL failover results in brief 503 window with automatic reconnection and zero data loss.

**Pre-requisites:**
- Staging Azure Database for PostgreSQL Flexible Server with HA enabled
- Staging app deployed and healthy
- Test data seeded (known record count for verification)

**Steps:**

1. **Baseline capture** — record current state:
   ```bash
   curl -sf https://app-qgp-staging.azurewebsites.net/readyz | jq .
   BASELINE_COUNT=$(curl -sf https://app-qgp-staging.azurewebsites.net/api/v1/policies/ \
     -H "Authorization: Bearer $TOKEN" | jq '.total')
   echo "Baseline policy count: $BASELINE_COUNT"
   ```

2. **Initiate planned failover:**
   ```bash
   az postgres flexible-server restart \
     --resource-group rg-qgp-staging \
     --name psql-qgp-staging \
     --failover Planned
   ```

3. **Monitor availability** — poll readiness in a loop:
   ```bash
   for i in $(seq 1 60); do
     STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
       https://app-qgp-staging.azurewebsites.net/readyz)
     echo "$(date +%H:%M:%S) readyz=$STATUS"
     sleep 5
   done
   ```

4. **Verify recovery:**
   - `/readyz` returns 200 with `"database": "connected"` within 120s
   - `/healthz` returns 200
   - API queries return expected data

5. **Verify zero data loss:**
   ```bash
   POST_COUNT=$(curl -sf https://app-qgp-staging.azurewebsites.net/api/v1/policies/ \
     -H "Authorization: Bearer $TOKEN" | jq '.total')
   echo "Post-failover policy count: $POST_COUNT (expected: $BASELINE_COUNT)"
   ```

**Expected Outcome:** Brief 503 window (< 120s); connections re-established automatically; no data loss; no manual intervention required.

**Acceptance Criteria:**
- [ ] 503 window is < 120 seconds
- [ ] `/readyz` automatically recovers to 200
- [ ] Record count matches baseline (zero data loss)
- [ ] No unhandled exceptions in Application Insights
- [ ] Connection pool recovers without app restart

---

### Scenario 6: Network Partition (API ↔ DB) — Procedure Documented — Execution Scheduled Q2 2026

**Objective:** Confirm that a network partition between the API and database triggers circuit breaker behavior and prevents cascade failures.

**Pre-requisites:**
- Staging environment with VNet integration
- NSG (Network Security Group) on the database subnet
- Monitoring dashboard open

**Steps:**

1. **Baseline capture:**
   ```bash
   curl -sf https://app-qgp-staging.azurewebsites.net/readyz | jq .
   curl -sf https://app-qgp-staging.azurewebsites.net/healthz | jq .
   ```

2. **Inject network partition** — block PostgreSQL port via NSG rule:
   ```bash
   az network nsg rule create \
     --resource-group rg-qgp-staging \
     --nsg-name nsg-qgp-db-staging \
     --name block-postgres-chaos \
     --priority 100 \
     --direction Inbound \
     --access Deny \
     --protocol Tcp \
     --destination-port-ranges 5432 \
     --description "Chaos test: network partition"
   ```

3. **Observe behavior** — poll endpoints for 3 minutes:
   ```bash
   for i in $(seq 1 36); do
     HEALTH=$(curl -s -o /dev/null -w "%{http_code}" \
       https://app-qgp-staging.azurewebsites.net/healthz)
     READY=$(curl -s -o /dev/null -w "%{http_code}" \
       https://app-qgp-staging.azurewebsites.net/readyz)
     API=$(curl -s -o /dev/null -w "%{http_code}" \
       https://app-qgp-staging.azurewebsites.net/api/v1/policies/ \
       -H "Authorization: Bearer $TOKEN")
     echo "$(date +%H:%M:%S) healthz=$HEALTH readyz=$READY api=$API"
     sleep 5
   done
   ```

4. **Verify degraded behavior:**
   - `/readyz` returns 503 (database unreachable)
   - `/healthz` returns 503 (DB is a liveness dependency)
   - API endpoints return 503 with structured error (not timeouts or hangs)
   - No cascade to unrelated services

5. **Remove partition:**
   ```bash
   az network nsg rule delete \
     --resource-group rg-qgp-staging \
     --nsg-name nsg-qgp-db-staging \
     --name block-postgres-chaos
   ```

6. **Verify recovery** — confirm endpoints return to healthy state within 60s.

**Expected Outcome:** API returns 503 immediately (circuit breaker); no hung connections or thread pool exhaustion; automatic recovery when partition is removed.

**Acceptance Criteria:**
- [ ] API returns 503 within 30s of partition (not timeout)
- [ ] No thread pool exhaustion or memory growth
- [ ] Recovery within 60s of partition removal
- [ ] Application Insights shows circuit breaker activation
- [ ] No manual restart required

---

### Scenario 7: Disk Full on App Service — Procedure Documented — Execution Scheduled Q2 2026

**Objective:** Verify that log rotation prevents disk exhaustion and that alerts fire before reaching critical thresholds.

**Pre-requisites:**
- Staging App Service deployed
- Azure Monitor alerts configured for disk usage
- SSH/Kudu access to staging app

**Steps:**

1. **Baseline capture** — check current disk usage:
   ```bash
   az webapp ssh --resource-group rg-qgp-staging --name app-qgp-staging
   # Inside SSH session:
   df -h /home
   du -sh /home/LogFiles/*
   ```

2. **Simulate disk pressure** — create large files in the temp directory:
   ```bash
   # Inside SSH/Kudu session:
   dd if=/dev/zero of=/home/site/wwwroot/chaos-test-fill.tmp bs=1M count=500
   df -h /home
   ```

3. **Verify alert fires:**
   - Check Azure Monitor for disk usage alert (threshold: 80%)
   - Verify alert routes to configured notification channel

4. **Verify application resilience:**
   ```bash
   curl -sf https://app-qgp-staging.azurewebsites.net/healthz | jq .
   curl -sf https://app-qgp-staging.azurewebsites.net/readyz | jq .
   ```

5. **Verify log rotation:**
   - Confirm log rotation is configured (check `/home/LogFiles/` size caps)
   - Verify old logs are pruned and new logs continue writing

6. **Cleanup** — remove test files:
   ```bash
   rm -f /home/site/wwwroot/chaos-test-fill.tmp
   df -h /home
   ```

7. **Verify recovery** — confirm disk usage returns to normal and alert clears.

**Expected Outcome:** Log rotation prevents full disk; alert fires at 80% threshold; application continues serving requests; cleanup restores normal operation.

**Acceptance Criteria:**
- [ ] Alert fires before disk reaches 90%
- [ ] Log rotation is active and prevents unbounded growth
- [ ] Application remains responsive during disk pressure
- [ ] `/healthz` returns 200 throughout test
- [ ] Disk usage returns to baseline after cleanup

---

## Execution Framework

1. **Environment**: Staging only (never production for chaos tests)
2. **Notification**: Team notified 24h before scheduled chaos test
3. **Duration**: Each scenario runs for max 5 minutes
4. **Monitoring**: Azure Monitor + application logs during test window
5. **Post-mortem**: Document results, unexpected behaviors, and remediation actions

## Related Documents

- [`docs/runbooks/on-call-guide.md`](../runbooks/on-call-guide.md) — incident response
- [`docs/runbooks/rollback.md`](../runbooks/rollback.md) — rollback procedures
- [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md) — drill results log
