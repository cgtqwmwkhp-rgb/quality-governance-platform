# Azure Static Web Apps Governance Policy

## Release-Blocking Gate

**Policy**: Azure SWA deploy job MUST be green before any PR can be merged.

### Required Status Checks (GitHub Branch Protection)

The following status checks are REQUIRED for merge to `main`:

| Check | Workflow | Required |
|-------|----------|----------|
| Build and Deploy Job | Azure Static Web Apps CI/CD | ✅ YES |
| Code Quality | CI | ✅ YES |
| Unit Tests | CI | ✅ YES |
| Integration Tests | CI | ✅ YES |
| Security Scan | Security Scan | ✅ YES |

### Configuration

To enforce this in GitHub Branch Protection:
1. Go to: Settings → Branches → main → Edit
2. Enable "Require status checks to pass before merging"
3. Add: "Build and Deploy Job"
4. Save changes

## NO MERGE IF SWA RED

**Rule**: If the Azure SWA workflow shows failure (red ❌), the following applies:

1. **DO NOT MERGE** the PR regardless of other checks passing
2. **INVESTIGATE** the failure root cause:
   - TypeScript/build errors → Fix code
   - Environment quota limit → Run cleanup (see `AZURE_SWA_ENVIRONMENT_CLEANUP.md`)
   - Azure configuration → Escalate to Azure admin
3. **RE-RUN** workflow after fix
4. **VERIFY GREEN** before proceeding with merge

## Environment Quota Management

### Limits

- **Free tier**: 3 staging environments maximum
- **Standard tier**: 10 staging environments maximum

### Automated Cleanup

A scheduled cleanup workflow runs:
- **Nightly at 02:00 UTC**: Deletes environments for closed/merged PRs
- **On PR close**: Immediate cleanup of that PR's environment

### Manual Cleanup

If automated cleanup fails or quota is exceeded:
1. Follow `AZURE_SWA_ENVIRONMENT_CLEANUP.md` runbook
2. Delete stale environments via Portal or CLI
3. Re-run failed workflow

## Incident Response

### Symptoms
- SWA deploy fails with "maximum number of staging environments"
- New PRs cannot deploy preview environments

### Response
1. **STOP**: Do not merge any PRs
2. **RUN**: Environment cleanup runbook
3. **VERIFY**: SWA deploy succeeds
4. **RESUME**: Normal merge process

### Escalation
If cleanup doesn't resolve issue:
- Contact Azure administrator
- Check Azure subscription status
- Review SWA tier limits

## Audit Trail

All environment deletions are logged in:
- GitHub Actions workflow logs
- Azure Activity Log

## Review Schedule

This policy is reviewed:
- After any SWA-related incident
- Quarterly as part of infrastructure review
