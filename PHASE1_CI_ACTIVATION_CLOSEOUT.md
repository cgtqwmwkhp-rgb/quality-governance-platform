# Phase 1: CI Activation Closeout

**Date**: 2026-01-04  
**Status**: ✅ **READY FOR ACTIVATION** (Manual workflow installation required)

---

## 1. Touched Files

- **Added**: `PHASE1_CI_ACTIVATION_CLOSEOUT.md` (this document)

---

## 2. What Changed and Why

This phase provides the final, detailed instructions for manually activating the GitHub Actions CI workflow. This is necessary due to GitHub App permission restrictions that prevent automated workflow creation.

---

## 3. Evidence Artifacts

### 3.1 Manual Installation Instructions

**Step 1: Navigate to Repository**
Go to: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform

**Step 2: Create Workflow File**
1. Click "Add file" → "Create new file"
2. In the filename field, type: `.github/workflows/ci.yml`

**Step 3: Copy Workflow Content**
Copy the complete workflow content from the attached file: `ci-workflow-for-manual-install.yml`

**Step 4: Commit**
1. Commit message: `Stage 0.4: Activate CI with blocking security gates`
2. Select "Commit directly to the main branch"
3. Click "Commit new file"

### 3.2 Required Evidence from First Live Run

Once the workflow is installed, the following evidence is required to proceed to Phase 2:

1. **GitHub Actions Run URL**: The full URL of the first successful CI run.
2. **Log Excerpts** (from the completed run):
   - **Integration Tests Job**:
     - Postgres startup confirmation
     - `alembic upgrade head` success message
     - `validate_quarantine.py` output
     - `pytest tests/integration/` summary (23 passed, 1 skipped)
   - **Security Scan Job**:
     - `validate_security_waivers.py` summary (1 CVE waived)
     - `bandit` summary (0 High severity issues)

### 3.3 Branch Protection Checklist

To ensure merge safety, the following branch protection rule must be configured for the `main` branch:

1. **Navigate to Settings**: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/settings/branches
2. **Add branch protection rule** for `main`
3. **Check the following boxes**:
   - [x] **Require a pull request before merging**
   - [x] **Require status checks to pass before merging**
     - [x] **Require branches to be up to date before merging**
     - [x] **Search for status checks**: `all-checks`

---

## 4. STOP CONDITION Met

**Yes**. Phase 1 is complete. I will now stop and wait for the following evidence before proceeding to Phase 2:

1. **GitHub Actions run URL** for the new workflow, with all jobs green.
2. **Confirmation** that the `main` branch protection rule requires the `all-checks` job to pass before merging.
