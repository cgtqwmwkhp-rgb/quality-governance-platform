# Branch Protection Evidence Checklist

**Date**: 2026-01-04

---

## 1. Objective

This document provides a checklist of the evidence that must be captured to prove that branch protection is correctly configured and enforced for the `main` branch.

---

## 2. Evidence to Capture

### 2.1. Screenshot: Branch Protection Rule

**What to capture**:
- The full branch protection rule settings for the `main` branch.
- Must clearly show:
  - `Require status checks to pass before merging` is **enabled**
  - `all-checks` is a **required** status check
  - `Include administrators` is **enabled**

**Where to store**: `docs/evidence/branch_protection_rule.png`

**What a compliant screenshot must show**:
- The GitHub repository settings page at `https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/settings/branches`
- A visible branch protection rule for the `main` branch
- The following settings must be clearly visible and enabled:
  - ✅ "Require a pull request before merging"
  - ✅ "Require status checks to pass before merging"
  - ✅ The status check named **`all-checks`** must be listed as required (case-sensitive, exact match)
  - ✅ "Require branches to be up to date before merging"
  - ✅ "Include administrators"
  - ❌ "Allow force pushes" must be disabled
  - ❌ "Allow deletions" must be disabled

### 2.2. Screenshot: Blocked PR

**What to capture**:
- A screenshot of a pull request where the "Merge pull request" button is disabled.
- Must clearly show the reason for the block (e.g., "Required status check \"all-checks\" is in progress" or "...has failed").

**Where to store**: `docs/evidence/blocked_pr.png`

**What a compliant screenshot must show**:
- A pull request page targeting the `main` branch
- The "Merge pull request" button must be visibly disabled (grayed out or not clickable)
- A message explaining why the merge is blocked, such as:
  - "Required status check 'all-checks' is expected" OR
  - "Required status check 'all-checks' has not run" OR
  - "Required status check 'all-checks' has failed" OR
  - "Merging is blocked"
- The status check section showing that `all-checks` is required and has not passed

### 2.3. Terminal Output: Direct Push Rejection

**What to capture**:
- The full terminal output from the `git push origin main` command.
- Must clearly show the `[remote rejected]` error message.

**Where to store**: `docs/evidence/direct_push_rejection.log`

**What a compliant log must show**:
- The command: `git push origin <branch>:main`
- The error message: `remote: error: GH006: Protected branch update failed for refs/heads/main`
- The rejection reason: `Changes must be made through a pull request`
- The rejection reason: `Required status check "all-checks" is expected`
- The final error: `[remote rejected] ... (protected branch hook declined)`

---

## 3. Operator Run Instructions

### Step 1: Configure Branch Protection

1. Navigate to your repository settings: `https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/settings/branches`
2. Click "Add rule" or edit the existing rule for `main`
3. Configure the following settings:
   - ✅ Require a pull request before merging (1 approval)
   - ✅ Require status checks to pass before merging
   - ✅ Add required status check: **`all-checks`** (case-sensitive, must match exactly)
   - ✅ Require branches to be up to date before merging
   - ✅ Include administrators
   - ❌ Allow force pushes (disabled)
   - ❌ Allow deletions (disabled)
4. Save the rule

### Step 2: Run Verification Script

```bash
cd /path/to/quality-governance-platform
./scripts/validate_evidence.sh
```

### Step 3: Capture Evidence

1. **Screenshot 1**: Branch protection rule page showing all settings
2. **Screenshot 2**: Pull request page showing blocked merge button with reason
3. **Terminal output**: Copy the direct push rejection error from your terminal

### Step 4: Store Evidence

Save the captured artifacts to `docs/evidence/` with the exact filenames:
- `branch_protection_rule.png`
- `blocked_pr.png`
- `direct_push_rejection.log`

## 4. Status Check Name Validation

**IMPORTANT**: The name of the required status check is **case-sensitive** and must match the name of the job in the CI workflow exactly.

- **Correct name**: `all-checks`
- **Incorrect names**: `All-Checks`, `all checks`, `All Checks`

An incorrect name will result in the branch protection rule not being enforced correctly.

## 5. Evidence Validation

After capturing the evidence, run the validation script to ensure all required files are present:

```bash
./scripts/validate_evidence.sh
```

This script checks for the presence of the three required evidence files. It does not validate the content of the files; that must be done manually by reviewing the screenshots and log against the requirements in sections 2.1, 2.2, and 2.3.
