# Environment Parity Verification (D31)

Evidence of staging-to-production configuration alignment.

## Environment Architecture

| Attribute | Staging | Production | Parity Status |
|-----------|---------|------------|---------------|
| App Service SKU | B1 | B2 | Different (acceptable — staging is smaller) |
| Python version | 3.11 | 3.11 | Aligned |
| Node version | 20 | 20 | Aligned |
| PostgreSQL version | 16 | 16 | Aligned |
| PostgreSQL SKU | Burstable B1ms | Burstable B1ms | Aligned |
| Redis | Basic C0 | Basic C0 | Aligned |
| Docker base image | `python:3.11-slim` | `python:3.11-slim` | Aligned |
| Region | UK South | UK South | Aligned |

## Configuration Parity

| Config Category | Mechanism | Drift Control |
|-----------------|-----------|---------------|
| Environment variables | Azure App Settings | `config-drift-guard` CI job |
| Feature flags | Database (per-environment) | Manual review |
| CORS origins | `src/main.py` (regex) | Code review |
| Database connection | Environment variable | Validated in `readyz` |
| Blob storage | Environment variable | Validated in service layer |

## Drift Controls

### config-drift-guard CI Job

The `config-drift-guard` job in `.github/workflows/ci.yml` validates that:
1. Required configuration files exist and are valid
2. Configuration schemas match between environments
3. No undocumented configuration keys are present

### Environment Variable Validation

The `config-failfast` pattern (see [ADR-0002](../adr/ADR-0002-config-failfast.md)) ensures:
1. All required environment variables are checked at startup
2. Missing variables cause a fast, clear failure with descriptive error messages
3. The same validation runs in both staging and production

## Deployment Parity

| Aspect | Staging | Production | Notes |
|--------|---------|------------|-------|
| Deploy trigger | Auto on merge to main | Gated (signoff required) | Intentional difference |
| Container image | Same ACR image | Same ACR image | Identical artifact |
| Health checks | `/healthz` + `/readyz` | `/healthz` + `/readyz` | Same endpoints |
| Alembic migrations | Run on deploy | Run on deploy | Same migration chain |
| Frontend build | Same SWA artifact | Same SWA artifact | Identical artifact |

## Verification Checklist

- [ ] Build SHAs match between staging and production after deploy
- [ ] Health endpoints return 200 in both environments
- [ ] Database migration versions are identical (`alembic current`)
- [ ] Feature flag states documented and reviewed
- [ ] No orphan environment variables in either environment

## Related Documents

- [`docs/adr/ADR-0002-config-failfast.md`](../adr/ADR-0002-config-failfast.md) — config validation
- [`docs/adr/ADR-0006-environment-and-config-strategy.md`](../adr/ADR-0006-environment-and-config-strategy.md) — env strategy
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — config-drift-guard job
- [`.github/workflows/deploy-staging.yml`](../../.github/workflows/deploy-staging.yml) — staging deploy
- [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) — production deploy
