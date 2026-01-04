# Branch Protection Verification Pack

**Date**: 2026-01-04

---

## 1. Objective

This document provides the exact steps for the repository owner to verify that branch protection rules are correctly configured for the `main` branch. This is a critical component of our release governance strategy, ensuring that all code merged to `main` has passed all required quality and security gates.

---

## 2. Required Branch Protection Settings

**Repository**: `cgtqwmwkhp-rgb/quality-governance-platform`  
**Branch**: `main`

Navigate to `Settings > Branches > Branch protection rules` and ensure a rule for `main` is configured with the following settings:

| Setting | Required Value | Rationale |
|---|---|---|
| **Require a pull request before merging** | ✅ Enabled | All changes must be reviewed and approved via a PR. |
| **Require approvals** | ✅ Enabled (1 approval) | Ensures at least one other team member has reviewed the code. |
| **Require status checks to pass before merging** | ✅ Enabled | All CI gates must pass before a merge is allowed. |
| **Require branches to be up to date before merging** | ✅ Enabled | Prevents merging stale branches with potential conflicts. |
| **Require conversation resolution before merging** | ✅ Enabled | Ensures all review comments are addressed. |
| **Require linear history** | ✅ Enabled | Prevents merge commits and keeps history clean. |
| **Include administrators** | ✅ Enabled | Enforces these rules for repository administrators as well. |
| **Restrict who can push to matching branches** | ✅ Enabled | Only allow specific users/teams to push (optional but recommended). |
| **Allow force pushes** | ❌ Disabled | Prevents rewriting history on the `main` branch. |
| **Allow deletions** | ❌ Disabled | Prevents accidental deletion of the `main` branch. |

### Status Checks

The following status check **must** be required:

- `all-checks`

This ensures that the final aggregator job, which depends on all other jobs, has passed successfully.

---

## 3. Verification Steps

### 3.1. Verify Direct Push Rejection

**Objective**: Confirm that direct pushes to `main` are blocked.

**Steps**:
1. Clone the repository locally.
2. Create a new file: `touch direct_push_test.txt`
3. Add and commit the file: `git add . && git commit -m "Test: direct push to main"`
4. Attempt to push directly to `main`: `git push origin main`

**Expected Result**:
The push should be rejected with an error message similar to this:

```
! [remote rejected] main -> main (protected branch hook declined)
error: failed to push some refs to 'https://github.com/cgtqwmwkhp-rgb/quality-governance-platform.git'
```

### 3.2. Verify Blocked PR (Incomplete Checks)

**Objective**: Confirm that a PR cannot be merged if CI checks have not completed or have failed.

**Steps**:
1. Create a new branch: `git checkout -b test/blocked-pr`
2. Create a new file and commit it: `touch blocked_pr_test.txt && git add . && git commit -m "Test: blocked PR"`
3. Push the branch: `git push origin test/blocked-pr`
4. Open a pull request from `test/blocked-pr` to `main`.

**Expected Result**:
The "Merge pull request" button should be disabled with a message indicating that status checks have not passed (or are in progress).

---

## 4. Why This is Non-Negotiable

Branch protection is the final and most critical enforcement mechanism for our CI-driven governance model. Without it, all the quality gates we have built into our CI pipeline can be bypassed.

- **Prevents Unvetted Code**: Ensures that no code reaches `main` without passing all automated checks and human review.
- **Maintains a Stable Mainline**: A green `main` branch means we can release with confidence at any time.
- **Enforces Accountability**: PRs provide a clear audit trail of who proposed, reviewed, and approved every change.

By locking down the `main` branch, we transform our CI pipeline from a set of recommendations into a set of **unbreakable rules**.
