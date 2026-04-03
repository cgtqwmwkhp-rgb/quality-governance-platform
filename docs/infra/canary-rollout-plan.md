# Canary Rollout Plan (D18)

Progressive delivery strategy for production deployments.

## Current Deployment Model

| Stage | Environment | Mechanism | Verification |
|-------|-------------|-----------|--------------|
| 1 | Staging | Auto-deploy on merge to main | Automated smoke tests |
| 2 | Production | Gated deploy (signoff required) | Health checks + slot swap |

## Deployment Slot Strategy

Azure App Service deployment slots provide zero-downtime deployments:

1. **Deploy to staging slot** — new version deployed without affecting production traffic
2. **Warm-up** — staging slot receives warm-up requests to initialize application
3. **Swap** — production and staging slots are swapped atomically (~8s)
4. **Rollback** — if issues detected, swap back to previous slot

## Canary Rollout Timeline

| Phase | Traffic Split | Duration | Success Criteria | Rollback Trigger |
|-------|--------------|----------|------------------|------------------|
| Deploy to slot | 0% to new version | Immediate | Slot health check passes | Slot health check fails |
| Warm-up | 0% (warm-up requests only) | 2 minutes | Response times < SLO | Warm-up failures > 5% |
| Swap | 100% to new version | Instant | All health checks pass | Error rate > 1% post-swap |
| Monitor | 100% on new version | 15 minutes | p95 < 200ms, error < 0.5% | p95 > 500ms or error > 1% |
| Stable | 100% on new version | Ongoing | SLOs maintained | Incident declared |

## Rollback Procedure

1. **Immediate**: `az webapp deployment slot swap --resource-group qgp-rg --name app-qgp-prod --slot staging`
2. **Verification**: Check `/healthz` and `/readyz` return 200
3. **Communication**: Notify team of rollback and open incident for investigation

## Future Enhancements

| Enhancement | Status |
|-------------|--------|
| Automated rollback on health check failure | Planned |
| Traffic splitting (10%/50%/100%) | Planned (requires Azure Front Door or Traffic Manager) |
| Feature flag-gated rollout | Partially implemented (feature flag service exists) |

## Related Documents

- [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) — production deploy
- [`docs/runbooks/rollback-drills.md`](../runbooks/rollback-drills.md) — rollback procedures
- [`docs/evidence/release_signoff.json`](../evidence/release_signoff.json) — release gate
