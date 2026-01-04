# Branch Protection Evidence

This directory contains evidence artifacts that prove branch protection is correctly configured and enforced for the `main` branch.

## Required Artifacts

1. **branch_protection_rule.png** - Screenshot of the branch protection rule settings
2. **blocked_pr.png** - Screenshot of a blocked pull request
3. **direct_push_rejection.log** - Terminal output showing direct push rejection

## Operator Instructions

To generate this evidence, follow the steps in the [Branch Protection Evidence Checklist](../BRANCH_PROTECTION_EVIDENCE_CHECKLIST.md) and run the verification script:

```bash
./scripts/verify_branch_protection.sh
```

Capture the required screenshots and terminal output, then save them to this directory with the exact filenames listed above.
