# Operator Run Snippet - Branch Protection Evidence Capture

## Quick Start

Copy and paste the following commands to capture branch protection evidence:

```bash
# Navigate to repository root
cd /path/to/quality-governance-platform

# Run the verification script
./scripts/verify_branch_protection.sh

# The script will:
# 1. Attempt to push directly to main (should fail)
# 2. Create a test branch and push it
# 3. Optionally open a PR (if GitHub CLI is installed)
```

## Capture Evidence

### 1. Direct Push Rejection

The script output will show the direct push rejection. Copy the terminal output and save it to:

```bash
# Save the terminal output to:
docs/evidence/direct_push_rejection.log
```

### 2. Branch Protection Rule Screenshot

1. Navigate to: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/settings/branches
2. Take a screenshot showing the branch protection rule for `main`
3. Ensure the screenshot clearly shows:
   - Required status check: `all-checks` (case-sensitive)
   - Include administrators: enabled
4. Save the screenshot as: `docs/evidence/branch_protection_rule.png`

### 3. Blocked PR Screenshot

1. Navigate to the pull request created by the script
2. Take a screenshot showing the merge button is disabled
3. Ensure the screenshot clearly shows the reason (e.g., "Required status check 'all-checks' has not run")
4. Save the screenshot as: `docs/evidence/blocked_pr.png`

## Validate Evidence

After capturing all three artifacts, run the validator to confirm:

```bash
python3 scripts/validate_evidence.py
```

Expected output:
```
✅ FOUND: docs/evidence/branch_protection_rule.png
✅ FOUND: docs/evidence/blocked_pr.png
✅ FOUND: docs/evidence/direct_push_rejection.log
✅ VALIDATION PASSED
```

## Commit Evidence

Once all artifacts are captured and validated, commit them to the repository:

```bash
git add docs/evidence/
git commit -m "docs: add branch protection evidence artifacts"
git push origin main
```

**Note**: This push may be rejected if branch protection is already enabled. In that case, create a PR and merge it after CI passes.
