# Branch Protection Checklist

## Repository Settings URL
https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/settings/branches

## Required Settings for `main` Branch

### 1. Require a pull request before merging
- ✅ **Enable**: Require a pull request before merging
- ✅ **Require approvals**: Set to **1** (at least 1 reviewer)
- ✅ **Dismiss stale pull request approvals when new commits are pushed**: Enabled
- ⚠️ **Require review from Code Owners**: Optional (enable if CODEOWNERS file exists)

### 2. Require status checks to pass before merging
- ✅ **Enable**: Require status checks to pass before merging
- ✅ **Require branches to be up to date before merging**: Enabled
- ✅ **Status checks that are required**:
  - `all-checks` (the aggregator job from CI workflow)

### 3. Require conversation resolution before merging
- ✅ **Enable**: Require conversation resolution before merging

### 4. Require signed commits
- ⚠️ **Optional**: Enable if your organization requires signed commits

### 5. Require linear history
- ⚠️ **Optional**: Enable to prevent merge commits (enforces rebase/squash)

### 6. Do not allow bypassing the above settings
- ✅ **Disable**: "Allow specified actors to bypass required pull requests"
- ⚠️ **Note**: Only enable bypass for admins if absolutely necessary for emergency hotfixes

### 7. Restrict who can push to matching branches
- ⚠️ **Optional**: Enable to restrict direct pushes to specific users/teams

### 8. Allow force pushes
- ❌ **Disable**: Do not allow force pushes

### 9. Allow deletions
- ❌ **Disable**: Do not allow branch deletion

## Implementation Steps

1. Navigate to: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/settings/branches
2. Click "Add branch protection rule" (or edit existing rule for `main`)
3. In "Branch name pattern", enter: `main`
4. Enable all settings marked with ✅ above
5. In "Status checks that are required", search for and select: `all-checks`
6. Click "Create" or "Save changes"

## Verification

After applying the settings:
1. Attempt to push directly to `main` → Should be blocked
2. Create a PR and verify that the `all-checks` status check is required
3. Verify that at least 1 approval is required before merging

## Status
- [ ] Branch protection rule created
- [ ] `all-checks` status check required
- [ ] At least 1 approval required
- [ ] Bypass protections disabled for admins
- [ ] Verified by attempting direct push (should fail)
