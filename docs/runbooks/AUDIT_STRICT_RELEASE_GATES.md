# Audit Strict Release Gates

Version: 1.0  
Owner: Platform Engineering

## Gate Sequence

1. CI checks must pass on candidate SHA.
2. Staging deploy must succeed.
3. Staging smoke + audit lifecycle E2E must pass.
4. Governance UAT sign-off must be documented.
5. CAB approval must be documented.
6. Production deploy validates signed evidence and promotes same SHA.

## Immutable Promotion Rule

- For `workflow_run` production promotions, deployment uses `github.event.workflow_run.head_sha`.
- Production refuses to build a new image in that path and reuses the prebuilt SHA-tagged image.
- Deployment aborts if image tag for that SHA is missing in ACR.

## Signed Evidence Rule

Production deploy is blocked unless `docs/evidence/release_signoff.json`:

- Exists
- Matches expected release SHA
- Has `governance_lead_approved: true`
- Has `cab_approved: true`

Validation script:

- `scripts/governance/validate_release_signoff.py`
