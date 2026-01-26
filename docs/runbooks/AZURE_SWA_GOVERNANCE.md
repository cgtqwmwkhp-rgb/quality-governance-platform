# Azure Static Web Apps Governance Policy

## Release-Blocking Gate: NO MERGE IF SWA RED

**Policy**: The Azure SWA deploy job MUST be green before any PR can be merged to `main`.

This is enforced:
1. **Technically** via GitHub Branch Protection required status checks
2. **Procedurally** via this documented policy
3. **Automatically** via environment cleanup automation

---

## Required Status Checks (Branch Protection)

The following status checks MUST be configured as **REQUIRED** for merges to `main`:

| Status Check Name (Exact) | Workflow | Required |
|---------------------------|----------|----------|
| `Build and Deploy Job` | Azure Static Web Apps CI/CD | ✅ **YES** |
| `Code Quality` | CI | ✅ YES |
| `Unit Tests` | CI | ✅ YES |
| `Integration Tests` | CI | ✅ YES |
| `Smoke Tests (CRITICAL)` | CI | ✅ YES |
| `Security Scan` | Security Scan | ✅ YES |

### Admin Checklist: Enable Required Status Checks

If not already configured, an admin must:

1. Go to: **Settings** → **Branches** → **main** → **Edit**
2. Enable: **☑️ Require status checks to pass before merging**
3. Enable: **☑️ Require branches to be up to date before merging**
4. In the search box, add these exact check names:
   - `Build and Deploy Job`
   - `Code Quality`
   - `Unit Tests`
   - `Integration Tests`
   - `Smoke Tests (CRITICAL)`
5. Click **Save changes**

After this, GitHub will block merges if `Build and Deploy Job` is red.

---

## Environment Quota Management

### Limits

| Tier | Max Staging Environments |
|------|--------------------------|
| Free | 3 |
| Standard | 10 |

### Automated Cleanup

The `swa-environment-cleanup.yml` workflow:

| Trigger | Behavior |
|---------|----------|
| PR close | Deletes that PR's environment immediately |
| Nightly (02:00 UTC) | Deletes environments for closed PRs |
| Manual | Dry-run by default; requires `confirm=true` to execute |

### Safety Guarantees

- Production environment (`default`) is NEVER deleted
- Only environments from actual `az staticwebapp environment list` output are considered
- Dry-run mode outputs what would be deleted before any action
- Safety switch: `DISABLE_CLEANUP=true` prevents all deletions

---

## Incident Response: SWA Deploy Failure

### Symptoms
- Azure SWA workflow fails with "maximum number of staging environments"
- New PRs cannot deploy preview environments
- Existing PRs show SWA deploy as red

### Response Steps

1. **STOP**: Do not merge any PRs
2. **IDENTIFY**: Check which environments exist
   ```bash
   az staticwebapp environment list \
     --name purple-water-03205fa03 \
     --resource-group rg-qgp-prod \
     --output table
   ```
3. **RUN**: Follow `AZURE_SWA_ENVIRONMENT_CLEANUP.md` runbook
4. **VERIFY**: SWA deploy succeeds for affected PRs
5. **RESUME**: Normal merge process once all green

### Escalation

If cleanup doesn't resolve the issue:

| Level | Contact | When |
|-------|---------|------|
| L1 | Run cleanup runbook | Quota exceeded |
| L2 | Azure Portal admin | Cleanup fails |
| L3 | Azure Support | Resource issues |

---

## Merge Order for Infrastructure PRs

When infrastructure and feature PRs are both pending:

1. **Merge infrastructure PRs first** (e.g., governance hardening)
2. **Verify branch protection is active** (required checks enforced)
3. **Re-run feature PR** to confirm all checks green
4. **Then merge feature PR**

Example for current situation:
1. Merge PR #86 (infra/swa-governance-hardening) ← First
2. Confirm `Build and Deploy Job` is a required check
3. Re-run PR #85 workflows
4. Merge PR #85 (investigations) ← Second

---

## Audit Trail

All environment management actions are logged in:

- GitHub Actions workflow logs (`.github/workflows/swa-environment-cleanup.yml`)
- Azure Activity Log (accessible via Azure Portal)
- Cleanup workflow produces artifacts with deletion records

---

## Policy Review

This policy is reviewed:
- After any SWA-related incident
- After changes to Azure subscription or SWA tier
- Quarterly as part of infrastructure review

---

## Quick Reference

```
┌─────────────────────────────────────────────────────────────┐
│                    MERGE DECISION TREE                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Is "Build and Deploy Job" GREEN?                           │
│     │                                                       │
│     ├── YES → Proceed with merge                            │
│     │                                                       │
│     └── NO → STOP. Do not merge.                            │
│              │                                              │
│              ├── Error: "max staging environments"          │
│              │   → Run cleanup runbook                      │
│              │   → Re-run workflow                          │
│              │   → Verify green                             │
│              │                                              │
│              └── Other error                                │
│                  → Fix code issue                           │
│                  → Re-run workflow                          │
│                  → Verify green                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
