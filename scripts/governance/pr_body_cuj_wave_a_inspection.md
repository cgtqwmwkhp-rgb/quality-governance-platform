# Change Ledger — CUJ Wave A Inspection honesty + proof

## Summary
Closes residual world-class gaps on Inspection → Findings → CAPA → Risk: user-visible Flag-to-risk errors, scoped live-execute risk hand-off with stay-on-proof, Flag-to-risk Playwright, DownstreamWorkflowProof CTA after import promote, smoke asserts audit_finding CAPA (not incident bridge), UAT lifecycle assertions un-stubbed against harness contract.

## Change ledger
- Audits Flag-to-risk: toast on failure (Lens A honesty)
- AuditExecution: scoped `/risk-register?auditOnly=1&auditRef=` + Stay on proof
- Playwright: Flag-to-risk journey; import promote clicks View Audit Actions
- Smoke: complete_run → findings → audit_finding CAPA → optional risk query
- UAT: real path/status/data assertions (no vacuous stubs)

## Critical journeys
- CUJ-01 Inspection live execute → complete → proof → Actions/Risks
- CUJ-01 Findings Flag-to-risk → Risk Register
- CUJ import promote → DownstreamWorkflowProof CTAs

## Observability
- Operator-visible toast on Flag-to-risk failure (assertive live region via Toast)
- Smoke step names for list_run_findings / list_audit_finding_capa / list_risk_register_scoped

## Release plan
1. Squash-merge to main after CI green
2. Staging auto-deploy via CI workflow_run
3. Confirm staging tip + `/healthz` 200 (2×)
4. Force-deploy production with full 40-char `release_sha` (freeze window)

## Rollback plan
1. Revert squash commit on main
2. Redeploy previous known-good SHA via production workflow_dispatch
3. Verify `/api/v1/meta/version` matches rollback SHA

## Evidence pack
- AC-01: Flag-to-risk failure shows toast (not console-only)
- AC-02: Live complete proof risk link includes auditOnly + auditRef
- AC-03: Playwright Flag-to-risk + import promote CTA green
- CUJ-01: Inspection deep-links + live complete remain green
- CUJ-02: Import promote proof CTAs exercised
- Gate 0: Change ledger present
- Gate 1: Exclusive allowlist (Audits, AuditExecution, e2e specs, smoke, UAT)
- Gate 2: CI required checks
- Gate 3: Staging tip==SHA
- Gate 4: Prod tip==SHA
- Gate 5: Evidence recorded in this PR

## Test plan
- [ ] Frontend unit/e2e CI
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
