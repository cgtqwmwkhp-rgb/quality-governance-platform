# Governance Drift Prevention

**Stage**: 1.1  
**Purpose**: Prevent branch protection evidence from becoming stale or mismatched with CI workflow

---

## Overview

The branch protection snapshot (`docs/evidence/branch_protection_settings.json`) serves as machine-checkable evidence of governance settings. To prevent this evidence from drifting out of sync with actual GitHub settings or CI workflow configuration, we enforce two drift prevention rules:

1. **Snapshot Freshness**: Evidence must not be older than 30 days
2. **Workflow Coupling**: Required status checks must match CI workflow jobs

---

## Operational Rules

### Rule 1: Snapshot Freshness (< 30 Days)

**Requirement**: The branch protection snapshot must be refreshed at least every 30 days.

**Rationale**: Governance settings can change over time. A stale snapshot may not reflect current protections, creating a false sense of security.

**Enforcement**: CI will fail if the snapshot file is older than 30 days.

**Action Required**:
```bash
# Refresh the snapshot
./scripts/export_branch_protection.sh

# Commit the updated snapshot
git add docs/evidence/branch_protection_settings.json
git commit -m "chore: Refresh branch protection snapshot"
```

**Manual Override** (if snapshot cannot be refreshed):
```bash
# Create override file with expiry date and justification
echo "2026-01-15: Snapshot refresh blocked pending GitHub API maintenance" > docs/evidence/branch_protection_override.txt

# Commit the override
git add docs/evidence/branch_protection_override.txt
git commit -m "chore: Add branch protection snapshot override"
```

**Override Format**:
```
YYYY-MM-DD: Reason for keeping stale snapshot
```

**Override Expiry**: The override itself expires after 30 days from the specified date.

---

### Rule 2: Workflow Coupling

**Requirement**: The `all-checks` status check must be present in both:
- Branch protection snapshot (`required_status_checks.contexts`)
- CI workflow (`.github/workflows/ci.yml` jobs)

**Rationale**: Branch protection relies on the `all-checks` job as the blocking gate. If this job is renamed or removed from CI, branch protection becomes ineffective.

**Enforcement**: CI will fail if `all-checks` is missing from either location.

**Action Required** (if `all-checks` renamed in CI):
```bash
# 1. Update branch protection in GitHub UI to use new job name
# 2. Refresh the snapshot
./scripts/export_branch_protection.sh

# 3. Commit both changes
git add .github/workflows/ci.yml docs/evidence/branch_protection_settings.json
git commit -m "refactor: Rename all-checks job and update branch protection"
```

---

## Change Procedures

### Procedure A: Changing Branch Protection Settings

**When**: Modifying branch protection rules in GitHub (e.g., adding new required checks, changing approval count)

**Steps**:
1. Make changes in GitHub repository settings
2. Re-run export script: `./scripts/export_branch_protection.sh`
3. Commit updated snapshot in the **same PR** as related changes
4. CI will validate the new snapshot

**Example**:
```bash
# After changing branch protection in GitHub UI
./scripts/export_branch_protection.sh
git add docs/evidence/branch_protection_settings.json
git commit -m "chore: Update branch protection snapshot after adding new required check"
```

---

### Procedure B: Renaming or Removing CI Jobs

**When**: Renaming the `all-checks` job or removing it from CI workflow

**Steps**:
1. Update `.github/workflows/ci.yml` with new job name
2. Update branch protection in GitHub to require the new job name
3. Re-run export script: `./scripts/export_branch_protection.sh`
4. Commit all changes in the **same PR**
5. CI will validate the coupling

**Example**:
```bash
# After renaming all-checks to final-gate in CI
# AND updating branch protection in GitHub UI
./scripts/export_branch_protection.sh
git add .github/workflows/ci.yml docs/evidence/branch_protection_settings.json
git commit -m "refactor: Rename all-checks to final-gate and update branch protection"
```

---

### Procedure C: Routine Snapshot Refresh

**When**: Snapshot is approaching 30-day expiry (proactive refresh)

**Steps**:
1. Re-run export script: `./scripts/export_branch_protection.sh`
2. Commit updated snapshot
3. CI will validate freshness

**Example**:
```bash
# Proactive refresh before expiry
./scripts/export_branch_protection.sh
git add docs/evidence/branch_protection_settings.json
git commit -m "chore: Routine branch protection snapshot refresh"
```

---

## CI Integration

**Job**: `branch-protection-proof` (Stage 1.0)  
**Step**: `Check governance drift prevention (BLOCKING - Stage 1.1)`  
**Script**: `scripts/validate_branch_protection_drift.py`

**Validation Logic**:
1. Load snapshot from `docs/evidence/branch_protection_settings.json`
2. Check file modification time (< 30 days) OR valid override exists
3. Extract required checks from snapshot
4. Extract job names from `.github/workflows/ci.yml`
5. Verify `all-checks` present in both
6. Exit 0 if all checks pass, exit 1 if drift detected

**Exit Codes**:
- `0`: All drift prevention checks passed
- `1`: Drift detected (stale snapshot or workflow mismatch)

---

## Troubleshooting

### Error: "Branch protection snapshot is stale"

**Cause**: Snapshot file is older than 30 days

**Solution**:
```bash
./scripts/export_branch_protection.sh
git add docs/evidence/branch_protection_settings.json
git commit -m "chore: Refresh stale branch protection snapshot"
```

**Alternative** (if refresh not possible):
```bash
echo "$(date +%Y-%m-%d): [Reason for override]" > docs/evidence/branch_protection_override.txt
git add docs/evidence/branch_protection_override.txt
git commit -m "chore: Add snapshot override - [brief reason]"
```

---

### Error: "'all-checks' not in required status checks"

**Cause**: Branch protection in GitHub does not require the `all-checks` status check

**Solution**:
1. Go to GitHub repository settings → Branches → Branch protection rules
2. Edit the `main` branch rule
3. Under "Require status checks to pass before merging", add `all-checks`
4. Save changes
5. Refresh snapshot:
```bash
./scripts/export_branch_protection.sh
git add docs/evidence/branch_protection_settings.json
git commit -m "fix: Add all-checks to required status checks and refresh snapshot"
```

---

### Error: "'all-checks' job not found in CI workflow"

**Cause**: The `all-checks` job was renamed or removed from `.github/workflows/ci.yml`

**Solution**:
1. Restore the `all-checks` job in CI workflow, OR
2. Update branch protection to use the new job name, then refresh snapshot:
```bash
# After updating branch protection in GitHub
./scripts/export_branch_protection.sh
git add .github/workflows/ci.yml docs/evidence/branch_protection_settings.json
git commit -m "refactor: Update CI job name and branch protection"
```

---

## References

- [Branch Protection Evidence Checklist](./BRANCH_PROTECTION_EVIDENCE_CHECKLIST.md)
- [Stage 1.0 Acceptance Pack](./evidence/STAGE1.0_ACCEPTANCE_PACK.md)
- [Stage 1.1 Acceptance Pack](./evidence/STAGE1.1_ACCEPTANCE_PACK.md) (this stage)
