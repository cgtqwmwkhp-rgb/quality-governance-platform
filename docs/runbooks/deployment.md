# Runbook: Deployment Procedure

**Owner**: Platform Engineering
**Last Updated**: 2026-03-07
**Review Cycle**: Quarterly

---

## 1. Pre-Deployment Checklist

- [ ] All CI checks passing on the target commit (21+ jobs green)
- [ ] Release signoff completed (`docs/evidence/release_signoff.json`)
- [ ] CHANGELOG.md updated for this release
- [ ] No P0 security findings open
- [ ] Database migration tested in staging
- [ ] Rollback procedure reviewed

## 2. Staging Deployment

### Trigger
Push to `main` branch or manual dispatch via GitHub Actions.

### Automated Steps (deploy-staging.yml)
1. Environment guardrail validation
2. Azure Container Registry login and Docker build
3. Image digest capture for provenance
4. Preflight infrastructure check
5. Deploy to Azure App Service (staging slot)
6. Key Vault secret injection
7. ACI migration container runs `alembic upgrade head`
8. Health check retry loop (30 attempts, 10s interval)
9. Deterministic SHA verification (3 consecutive matches)
10. Deploy evidence capture (Markdown + JSON)
11. Post-deploy smoke tests
12. Audit lifecycle E2E test

### Verification
```
GET https://<staging-url>/healthz     → {"status": "ok"}
GET https://<staging-url>/readyz      → {"status": "ready", "database": "connected"}
GET https://<staging-url>/api/v1/meta/version → Verify build_sha matches
```

### Failure Response
- Health check failures → deployment automatically aborted; investigate via staging logs
- Smoke test failures → deployment marked as failed; do NOT promote to production

## 3. Production Deployment

### Trigger
After staging success (workflow_run), manual dispatch, or GitHub release.

### Pre-Production Gates
1. Staging deployment must have succeeded
2. Release signoff validation (`scripts/governance/validate_release_signoff.py`)
3. Production dependencies gate (database, Azure AD, Redis reachability)

### Automated Steps (deploy-production.yml)
1. Build or reuse staged image (digest verification)
2. Database backup via Azure automation
3. Deploy to Azure App Service (production)
4. Key Vault configuration injection
5. ACI migration container runs `alembic upgrade head`
6. Revision verification (correct image deployed)
7. Readiness-first health check (exponential backoff, 20-minute timeout)
8. Deterministic SHA verification (stability gate, 3 consecutive matches)
9. Deploy Proof v3:
   - Phase 1: Health and readiness
   - Phase 2: Identity verification (build SHA match)
   - Phase 3: OpenAPI latency check
   - Phase 4: Image provenance
   - Phase 5: Security headers and auth enforcement
10. Post-deploy security checks (CVE fix verification, rate limiting)

### Verification
```
GET https://<prod-url>/healthz
GET https://<prod-url>/readyz
GET https://<prod-url>/api/v1/meta/version → Verify SHA
POST https://<prod-url>/api/v1/tenants/ without auth → Must return 401
```

## 4. Post-Deployment

1. Monitor error rate for 30 minutes post-deploy
2. Verify DLQ depth remains at 0
3. Check circuit breaker states (all should be closed)
4. Confirm deploy evidence artifacts generated
5. Notify team in deployment channel

## 5. Emergency Deployment

For critical security patches:
1. Skip staging soak time (deploy directly after CI passes)
2. Require at least smoke tests to pass
3. Document reason for expedited deployment in release evidence
4. Post-deploy monitoring period extended to 60 minutes
