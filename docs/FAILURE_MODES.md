# Failure Mode Catalog

Comprehensive catalog of known failure modes, their impact, detection mechanisms,
and recovery procedures for the Quality Governance Platform.

---

## External Dependencies

### 1. PostgreSQL Unavailable
- **Impact:** All API endpoints return 503
- **Detection:** `/readyz` returns unhealthy, database check fails
- **Mitigation:** Automatic reconnection via SQLAlchemy connection pool (`pool_pre_ping=True`)
- **Recovery:** Restore database, restart app service
- **Runbook:** [Database Connection Exhaustion](./runbooks/database-connection-exhaustion.md)

### 2. Redis Unavailable
- **Impact:** Rate limiting falls back to in-memory (per-instance), caching disabled
- **Detection:** `/readyz` shows `redis: unavailable`
- **Mitigation:** Graceful degradation — app continues without cache, rate limiting uses in-memory fallback
- **Recovery:** Restart Redis, cache auto-warms on reconnection
- **Runbook:** [Redis Cache Failure](./runbooks/redis-cache-failure.md)

### 3. Email/SMS Service Down
- **Impact:** Notifications delayed, user invitations cannot be sent
- **Detection:** Circuit breaker opens after 5 consecutive failures
- **Mitigation:** Circuit breaker prevents cascade failure, queued notifications retry automatically
- **Recovery:** Service auto-retries when circuit half-opens (60s timeout)
- **User-facing:** Users see "notification pending" status; no data loss

### 4. AI Service (OpenAI/Anthropic) Down
- **Impact:** Copilot features unavailable, document AI extraction fails
- **Detection:** Circuit breaker opens after 3 consecutive failures
- **Mitigation:** Fallback to rule-based analysis for RIDDOR classification and risk scoring
- **Recovery:** Auto-recovers when circuit half-opens (120s timeout)
- **User-facing:** AI features show "temporarily unavailable" badge

### 5. Azure Blob Storage Unavailable
- **Impact:** Document uploads/downloads fail, file attachments inaccessible
- **Detection:** Upload API returns 503, `/readyz` shows `storage: unavailable`
- **Mitigation:** Upload queue buffers requests; existing metadata remains accessible
- **Recovery:** Azure-managed recovery; retry uploads after service restores
- **User-facing:** Upload button disabled with "storage unavailable" message

### 6. Azure AD / SSO Provider Down
- **Impact:** SSO login fails, new sessions cannot be created
- **Detection:** OAuth callback errors, login failure rate spike
- **Mitigation:** Users with active JWT sessions continue working until token expires
- **Recovery:** Azure-managed recovery; fallback to email/password login if configured
- **User-facing:** Login page shows "SSO temporarily unavailable, use email login"

---

## Internal Failures

### 7. Memory Pressure / OOM
- **Impact:** Container killed, in-flight requests lost
- **Detection:** Azure Container App / App Service liveness probe fails, restart counter increments
- **Mitigation:** Resource limits configured (512MB–1GB per instance), auto-restart by orchestrator
- **Recovery:** Container auto-restarts; investigate memory leaks via profiling
- **Investigation:** Check for unbounded query result sets, large file processing without streaming

### 8. Celery Worker Crash
- **Impact:** Background tasks delayed (reports, notifications, ETL imports)
- **Detection:** `/readyz` shows `celery: no_workers`, task queue depth increases
- **Mitigation:** Tasks persist in Redis/broker queue, processed when worker restarts
- **Recovery:** Worker auto-restarts via supervisor/container orchestrator
- **User-facing:** Background tasks show "processing" for longer than usual

### 9. Database Migration Failure
- **Impact:** Schema mismatch between app and database, potential 500 errors
- **Detection:** Application startup fails, Alembic reports migration conflict
- **Mitigation:** Deployment pipeline validates migrations before applying
- **Recovery:** Roll back migration (`alembic downgrade -1`), fix migration, redeploy
- **Runbook:** [Deployment Rollback](./runbooks/deployment-rollback.md)

### 10. Connection Pool Exhaustion
- **Impact:** New database queries queue and timeout, 503 responses
- **Detection:** `/readyz` database check fails, SQLAlchemy logs pool overflow warnings
- **Mitigation:** Pool configured with `pool_size=10, max_overflow=20, pool_timeout=30`
- **Recovery:** Identify and kill long-running queries, restart application
- **Runbook:** [Database Connection Exhaustion](./runbooks/database-connection-exhaustion.md)

---

## Security Failures

### 11. JWT Secret Compromise
- **Impact:** Attacker can forge authentication tokens
- **Detection:** Anomalous API access patterns, token validation anomalies
- **Mitigation:** Token blacklist table (`token_blacklist`) enables revocation
- **Recovery:** Rotate `JWT_SECRET_KEY`, blacklist all existing tokens, force re-login
- **User-facing:** All users must log in again

### 12. Rate Limit Bypass
- **Impact:** API abuse, potential DoS
- **Detection:** Anomalous request volume per user/IP in metrics
- **Mitigation:** Multi-layer rate limiting (Redis-backed + in-memory fallback)
- **Recovery:** Block offending IPs via Azure WAF, review rate limit configuration

### 13. Tenant Isolation Breach
- **Impact:** Cross-tenant data exposure (critical)
- **Detection:** Audit trail shows `tenant_id` mismatch in access patterns
- **Mitigation:** All queries filtered by `tenant_id` at the repository layer, validated in middleware
- **Recovery:** Identify breach scope, notify affected tenants, patch query path, conduct forensics

---

## Infrastructure Failures

### 14. TLS Certificate Expiry
- **Impact:** Browsers show security warnings, API clients reject connections
- **Detection:** Certificate monitoring alerts at 30/7 day thresholds
- **Mitigation:** Azure Managed Certificates auto-renew
- **Recovery:** Manual certificate renewal and binding
- **Runbook:** [Certificate Expiry](./runbooks/certificate-expiry.md)

### 15. DNS Resolution Failure
- **Impact:** Application unreachable via custom domain
- **Detection:** External health checks fail, uptime monitoring alerts
- **Mitigation:** Short TTL on DNS records, Azure Traffic Manager for failover
- **Recovery:** Verify DNS records, check domain registrar status

### 16. Azure Region Outage
- **Impact:** Full application unavailable
- **Detection:** Azure status page, external uptime monitoring
- **Mitigation:** DR plan documented in [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)
- **Recovery:** Failover to secondary region per DR plan, restore from geo-replicated backups

---

## Degradation Hierarchy

When multiple failures occur simultaneously, the platform degrades in this order:

| Priority | Component | Behaviour When Down |
|----------|-----------|---------------------|
| 1 | PostgreSQL | **Full outage** — all endpoints return 503 |
| 2 | Application | **Full outage** — no request processing |
| 3 | Redis | **Degraded** — slower responses, less accurate rate limiting |
| 4 | AI Services | **Partial** — AI features unavailable, core CRUD works |
| 5 | Email/SMS | **Partial** — notifications queued, all other features work |
| 6 | Blob Storage | **Partial** — file operations fail, metadata operations work |
| 7 | Celery Workers | **Partial** — background tasks delayed, synchronous API works |
