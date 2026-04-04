# CD workflow outcomes (staging / production)

## How to read GitHub Actions “success”

A workflow run can report **conclusion: success** while individual jobs are **skipped**. Always inspect the job graph before inferring that a new container was promoted.

### Deploy to Azure Production (`.github/workflows/deploy-production.yml`)

- **Build and Deploy to Production** — when this job is **skipped**, no new image was built or rolled out for that run. Typical causes include gated promotion (for example, signed `release_sha` / staging head checks) or branch conditions.
- **Pre-Deployment Checks** — may succeed while downstream deploy jobs are skipped; that still means “checks passed,” not “production updated.”
- **Authoritative evidence** for a real promotion: the **Build and Deploy to Production** job is **success**, including steps such as **Verify deployment - Readiness and Health checks** and deterministic SHA verification.

### Deploy to Azure Staging (`.github/workflows/deploy-staging.yml`)

- Expect **Build and Deploy to Staging** **success** for a real staging rollout.
- **Staging Smoke Tests** (when present) provide additional post-deploy verification.

### Release sign-off artifact

Cross-check `docs/evidence/release_signoff.json` with the **production** workflow run IDs recorded in GitHub Actions. Update the sign-off when promoting a new `release_sha`.

### Rollback

Emergency path: `.github/workflows/rollback-production.yml` (`workflow_dispatch`).
