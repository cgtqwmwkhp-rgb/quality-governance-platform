# Deployment Runbook (Quick Reference)

**Full runbook**: See [PRODUCTION_DEPLOYMENT_RUNBOOK.md](./PRODUCTION_DEPLOYMENT_RUNBOOK.md)

---

## Quick Deploy Steps

### Staging (automatic)

1. Push to `main` branch
2. CI pipeline runs (25+ jobs)
3. On CI success, staging deploy triggers automatically
4. Health verification runs (30 retries, exponential backoff)
5. Deterministic SHA verification (3 consecutive matches)

### Production (manual trigger or auto after staging)

1. Ensure `docs/evidence/release_signoff.json` is committed with:
   - `release_sha` matching HEAD
   - `governance_lead_approved: true`
   - `cab_approved: true`
   - Different approvers for governance and CAB
2. Trigger via GitHub Actions:
   ```bash
   gh workflow run deploy-production.yml \
     --field staging_verified=true \
     --field reason="Release description"
   ```
3. Pipeline executes:
   - `prod-dependencies-gate` (Key Vault, Storage, WebApp checks)
   - Release sign-off validation
   - Pre-deploy database backup
   - Image deploy by digest (not tag)
   - Database migrations via ACI
   - Health + readiness verification
   - Deterministic SHA verification
   - Security verification (auth enforcement, CVE check)
   - Deploy-proof artifact generation

### Rollback

See [rollback.md](./rollback.md) and [AUDIT_ROLLBACK_DRILL.md](./AUDIT_ROLLBACK_DRILL.md)

```bash
az webapp config container set \
  --name <WEBAPP_NAME> \
  --resource-group <RG_NAME> \
  --docker-custom-image-name <ACR>.azurecr.io/qgp:<ROLLBACK_SHA>
```

### Verification Endpoints

| Endpoint | Expected |
|----------|----------|
| `/healthz` | `200 OK` |
| `/readyz` | `200` with `database: ok`, `redis: ok` |
| `/api/v1/meta/version` | `build_sha` matches deployed SHA |
