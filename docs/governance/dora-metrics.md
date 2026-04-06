# DORA Metrics Tracking

## Metrics Definitions

| Metric | Definition | Current Measurement | Target |
|--------|-----------|-------------------|--------|
| Lead Time for Changes | Time from commit to production deploy | ~2-4 hours (CI + manual signoff) | < 1 hour |
| Deployment Frequency | How often code deploys to production | 2-5 per week | Daily |
| Mean Time to Recovery (MTTR) | Time to restore service after incident | ~8 seconds (slot swap) | < 5 minutes |
| Change Failure Rate | % of deployments causing incidents | < 5% (estimated) | < 5% |

## Measurement Approach
- Lead time tracked via GitHub Actions workflow duration
- Deployment frequency tracked via `deploy-production.yml` run history
- MTTR validated via rollback drills (see `docs/runbooks/rollback-drills.md`)
- Change failure rate tracked via incident correlation with deploy timestamps

## Review Cadence
Monthly review in engineering standup. Quarterly trend report for SLT.

**Last updated:** 2026-04-03
