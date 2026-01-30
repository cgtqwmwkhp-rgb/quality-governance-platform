# Azure Static Web Apps Deployment Policy

**Module**: CI/CD Governance  
**Version**: 1.0  
**Last Updated**: 2026-01-30

---

## Overview

Azure Static Web Apps (SWA) has a limit on staging/preview environments. This policy defines when SWA deployments are triggered and how to manage environment capacity.

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
```

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

---

## 5. Compensating Controls

For PRs that skip SWA deployment:

| Control | Enforcement |
|---------|-------------|
| Frontend changes | Detected by `dorny/paths-filter` |
| Staging smoke test | Required before production deploy |
| E2E tests | Run against staging in release workflow |

---

**Policy Owner**: Platform Team  
**Review Cycle**: Quarterly
