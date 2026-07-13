# Azure Static Web Apps Deployment Policy

**Module**: CI/CD Governance  
**Version**: 1.2  
**Last Updated**: 2026-07-13  
**ADR Reference**: ADR-0003 (SWA Gating Exception)

---

## Overview

Azure Static Web Apps (SWA) has a limit on staging/preview environments. This policy defines when SWA deployments are triggered and how to manage environment capacity.

**GOVERNED EXCEPTION**: Build & Deploy Job may fail for PRs that do not modify frontend source code. This is non-blocking when all quality gates pass. See Section 5 for compensating controls.

**tip==LIVE (env integrity)**: The user-facing SWA hostname
`https://purple-water-03205fa03.6.azurestaticapps.net` is production UI.
After a successful push-to-main SWA workflow, the default environment MUST bake
`VITE_API_URL=https://app-qgp-prod.azurewebsites.net` (see
`deploy_production_swa` in `.github/workflows/azure-static-web-apps-purple-water-03205fa03.yml`).
PR validation and the temporary pre-gate bake continue to use the staging API.

---

## 1. Deployment Triggers

### Automatic SWA Deployment

SWA preview environments are created **only** when PRs modify:
- `frontend/**` - Frontend source code
- `.github/workflows/azure-static-web-apps-*.yml` - SWA workflow

### Skipped Deployments

PRs that modify **only** the following paths will **skip** SWA deployment:
- `scripts/**` - Backend tooling
- `tests/**` - Test files
- `docs/**` - Documentation
- `src/**` - Backend API (deployed separately)

This prevents unnecessary preview environment creation for backend-only changes.

---

## 2. Environment Limits

| Plan | Staging Environments | Production |
|------|---------------------|------------|
| Free | 3 | 1 |
| Standard | 10 | 1 |

### Current Configuration

```yaml
SWA_APP_NAME: purple-water-03205fa03
RESOURCE_GROUP: rg-qgp-prod
PRODUCTION_API_URL: https://app-qgp-prod.azurewebsites.net
STAGING_API_URL: https://qgp-staging-plantexpand.azurewebsites.net
```

### Bake semantics (same hostname)

| Phase | Trigger | `VITE_API_URL` | Deployed to purple-water? |
|-------|---------|----------------|---------------------------|
| PR validation | `pull_request` | Staging API | No (build-only) |
| Staging verification | `push` to main | Staging API | Yes (temporary) |
| Production tip==LIVE | After staging UI gate | Production API | Yes (steady state) |

---

## 3. Cleanup Policy

### Automatic Cleanup

- **On PR Close/Merge**: The `close_pull_request_job` deletes the preview environment
- **Nightly Schedule**: `swa-environment-cleanup.yml` runs at 02:00 UTC
- **Manual Trigger**: Workflow dispatch with confirmation

### Manual Cleanup

```bash
# List current environments
az staticwebapp environment list \
  --name purple-water-03205fa03 \
  --resource-group rg-qgp-prod \
  --output table

# Delete specific environment
az staticwebapp environment delete \
  --name purple-water-03205fa03 \
  --resource-group rg-qgp-prod \
  --environment-name <env-number> \
  --yes
```

---

## 4. Troubleshooting

### "Maximum number of staging environments" Error

**Symptoms**:
```
The content server has rejected the request with: BadRequest
Reason: This Static Web App already has the maximum number of staging environments
```

**Resolution**:
1. **Immediate**: Trigger manual cleanup
   ```bash
   gh workflow run swa-environment-cleanup.yml -f confirm=CONFIRM
   ```

2. **Verify**: Check if PR modifies frontend files
   - If NO → deployment was correctly skipped (after fix)
   - If YES → cleanup needed

3. **Long-term**: Ensure PRs are closed/merged promptly

### tip==LIVE mismatch (UI talks to staging API)

**Symptoms**: Browser Network tab on purple-water shows calls to
`qgp-staging-plantexpand.azurewebsites.net` instead of `app-qgp-prod.azurewebsites.net`.

**Resolution**:
1. Confirm the latest successful main run of `Azure Static Web Apps CI/CD` completed
   `Deploy Production SWA (prod API bake)`.
2. Hard-refresh / clear SW cache, then re-check the inlined `VITE_API_URL` in the
   main JS bundle (must not bake staging outside the static `API_URLS.staging` map).
3. Re-run the workflow on main if the production bake job was skipped (e.g. validation mode).

---

## 5. Compensating Controls

For PRs that skip SWA deployment:

| Control | Enforcement |
|---------|-------------|
| Frontend changes | Detected by `dorny/paths-filter` |
| Staging smoke test | Required before production deploy |
| E2E tests | Run against staging bake in SWA workflow before prod API redeploy |

---

**Policy Owner**: Platform Team  
**Review Cycle**: Quarterly
