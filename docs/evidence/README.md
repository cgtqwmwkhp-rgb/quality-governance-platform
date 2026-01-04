# Evidence Directory

This directory contains governance evidence artifacts that prove the platform meets required security and operational standards.

## Branch Protection Evidence

### Machine-Checkable Proof (Stage 1.0)

**File**: `branch_protection_settings.json`

This file contains the branch protection settings for the `main` branch, exported via the GitHub API. It serves as machine-checkable proof that branch protection is configured correctly.

**How to Update**:
```bash
# Run the export script locally (requires appropriate GitHub permissions)
./scripts/export_branch_protection.sh

# Commit the updated file
git add docs/evidence/branch_protection_settings.json
git commit -m "Update branch protection settings evidence"
```

**CI Validation**:
The `branch-protection-proof` job in CI validates this file to ensure:
- Required status check `all-checks` is enforced
- Pull request reviews are required (>= 1 approval)
- Administrators cannot bypass branch protection  
- Force pushes are disabled
- Branch deletions are disabled

### Screenshot-Based Evidence (Stage 0.7)

The following files provide visual evidence of branch protection configuration:
- `branch_protection_rule.png` - Primary screenshot showing all settings
- `branch_protection_rule_part1.png` - Top section (branch name, PR requirements)
- `branch_protection_rule_part2.png` - Middle section (status checks)
- `branch_protection_rule_part3.png` - Bottom section (admin enforcement, force push/deletion settings)
- `blocked_pr.png` - Screenshot of a PR blocked by branch protection
- `direct_push_rejection.log` - Terminal output showing direct push rejection

## Operator Instructions

To generate the required evidence artifacts:

1. **Machine-checkable proof**: Run `./scripts/export_branch_protection.sh`
2. **Screenshot evidence**: Follow the steps in [Branch Protection Evidence Checklist](../BRANCH_PROTECTION_EVIDENCE_CHECKLIST.md)

## Maintenance

**When branch protection settings change**, both types of evidence must be updated:

1. **Machine-checkable proof**: Run `./scripts/export_branch_protection.sh` and commit the updated JSON file
2. **Screenshot evidence**: Capture new screenshots following the checklist instructions

The machine-checkable proof is the **source of truth** for CI validation. Screenshots serve as supplemental human-readable evidence.
