# Runbook: Production Rollback

**Owner**: Platform Engineering
**Last Updated**: 2026-03-07
**Review Cycle**: Quarterly

---

## 1. Trigger Conditions

- Post-deploy health checks failing for > 5 minutes
- Error rate > 5% after deployment
- SEV-1 incident traced to latest deployment
- Data integrity issue introduced by new migration
- Security vulnerability discovered in deployed code

## 2. Decision Authority

| Scenario | Who Can Authorize |
|----------|------------------|
| Automated (health check failure) | System (automatic via deploy workflow) |
| Manual (performance degradation) | Engineering Lead or On-Call Engineer |
| Emergency (security incident) | Any Senior Engineer + post-hoc approval |

## 3. Rollback Procedure

### Option A: GitHub Actions Rollback Workflow (Preferred)

1. Navigate to GitHub Actions → `rollback-production.yml`
2. Click "Run workflow"
3. Select the last known good image digest (from previous deploy evidence)
4. Workflow executes:
   - Redeploys previous image to Azure App Service
   - Runs health checks
   - Verifies SHA matches rollback target
   - Generates rollback evidence

### Option B: Azure Portal Manual Rollback

1. Azure Portal → App Service → Deployment Center
2. Identify previous successful deployment
3. Redeploy previous revision
4. Verify via `/api/v1/meta/version`

### Option C: Database Migration Rollback

If the issue is caused by a database migration:

```bash
# Connect to ACI migration container
az container exec --name qgp-migrate-prod --exec-command "alembic downgrade -1"
```

**WARNING**: Only downgrade if the migration has a working `downgrade()` function. Check the migration file first.

## 4. Verification After Rollback

1. `GET /healthz` → 200 OK
2. `GET /readyz` → 200 OK with database connected
3. `GET /api/v1/meta/version` → SHA matches rollback target
4. Monitor error rate for 15 minutes → should return to baseline
5. Check DLQ depth → should not be growing
6. Verify auth enforcement → `POST /api/v1/tenants/` without auth returns 401

## 5. Post-Rollback Actions

1. **Communicate**: Notify team that rollback occurred and why
2. **Preserve evidence**: Save deploy evidence from both the failed and rollback deployments
3. **Root cause**: Create incident ticket; investigate within 24 hours
4. **Fix forward**: Apply fix to main branch; deploy via normal process
5. **Update runbook**: Add any new learnings

## 6. Rollback Limitations

- Database migrations that drop columns/tables cannot be reversed
- Data written by the new version may reference schema that no longer exists after downgrade
- External integrations (webhook registrations, etc.) may need manual cleanup
- Feature flags enabled during the deployment remain enabled
