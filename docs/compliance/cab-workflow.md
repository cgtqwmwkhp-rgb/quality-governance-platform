# Change Advisory Board (CAB) Workflow (D08)

Documentation of the change approval process for production deployments.

## Current Change Approval Process

| Step | Action | Actor | Evidence |
|------|--------|-------|----------|
| 1 | PR created with change ledger | Developer | GitHub PR body template |
| 2 | CI gates pass (25+ checks) | Automated | `all-checks` job in `ci.yml` |
| 3 | Code review approval | Peer reviewer | GitHub PR approval |
| 4 | Release signoff SHA recorded | Release manager | `docs/evidence/release_signoff.json` |
| 5 | Staging deployment + verification | Automated | `deploy-staging.yml` workflow |
| 6 | Production deployment | Automated (gated) | `deploy-production.yml` workflow |

## Release Signoff Gate

The `release_signoff.json` file acts as a lightweight CAB approval mechanism:

```json
{
  "release_sha": "<approved commit SHA>",
  "governance_lead": "<name or id>",
  "governance_lead_approved": true,
  "cab_chair": "<name or id>",
  "cab_approved": true,
  "uat_report_path": "<path to UAT evidence>",
  "rollback_drill_path": "<path to rollback drill evidence>",
  "approved_at_utc": "<ISO-8601 timestamp in UTC>"
}
```

Required keys and types match `REQUIRED_FIELDS` in `scripts/governance/validate_release_signoff.py`.

Production deployment is blocked unless the merge commit SHA matches the signed-off SHA.

## Change Categories

| Category | Approval Required | Deployment Window |
|----------|-------------------|-------------------|
| Standard (feature, bug fix) | PR approval + signoff | Any time |
| Emergency (P0 incident fix) | Post-hoc approval allowed | Immediate |
| Infrastructure (DB migration, config) | PR approval + signoff + migration review | Business hours preferred |

## CAB Automation Plan

| Phase | Enhancement | Status |
|-------|-------------|--------|
| Phase 1 | PR template with required change ledger sections | Done |
| Phase 2 | Automated signoff validation in CI | Done |
| Phase 3 | Slack/Teams notification on deployment approval | Planned |
| Phase 4 | Automated rollback on post-deploy health check failure | Done (`deploy-production.yml` auto-rollback step) |

## Related Documents

- [`docs/evidence/release_signoff.json`](../evidence/release_signoff.json) — current signoff
- [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) — prod deploy
- [`scripts/governance/pr_body_template.md`](../../scripts/governance/pr_body_template.md) — PR template
