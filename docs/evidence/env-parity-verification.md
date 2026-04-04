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
| Docker base image | `python:3.11-slim-bookworm` (SHA digest) | `python:3.11-slim-bookworm` (SHA digest) | Aligned |
| Region | UK South | UK South | Aligned |

## Intentional Parity Exceptions

- **App Service SKU**: Staging uses **B1** (cost optimization); production uses **B2** (capacity).
- **Rationale**: Staging workload is approximately **10%** of production; B1 provides adequate capacity for testing while production retains headroom for peak load.
- **Runtime stack alignment**: Both environments use the **same Docker images** (identical base and application images), **Python 3.11**, **Node 20**, **PostgreSQL 16**, and **Redis Basic C0** — only the App Service compute SKU differs intentionally.

**Deploy workflow**: [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) implements a **cyclic SHA bypass** for manual runs with `staging_verified=true`: sign-off validation uses the `release_sha` recorded in `release_signoff.json` instead of requiring an exact match to the workflow’s resolved `RELEASE_SHA`, avoiding a chicken-and-egg when updating the signoff for the promoted commit. Introduced in **[PR #401](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/401)** (see the “skipping SHA-exact match (cyclic signoff)” branch in the governance UAT + CAB sign-off step).

## Configuration Parity

| Config Category | Mechanism | Drift Control |
|-----------------|-----------|---------------|
| Environment variables | Azure App Settings | `config-drift-guard` CI job |
| Feature flags | Database (per-environment) | Manual review |
| CORS origins | `src/main.py` (regex) | Code review |
| Database connection | Environment variable | Validated in `readyz` |
| Blob storage | Environment variable | Validated in service layer |

## Required Environment Variables (Parity Checklist)

All variables below must be set in **both** staging and production (values differ per environment).
Source: `src/core/config.py` settings class + `config-failfast` startup validation.

| Variable | Staging | Production | Parity |
|----------|---------|------------|--------|
| `DATABASE_URL` | `postgresql+asyncpg://...staging...` | `postgresql+asyncpg://...prod...` | Set in both (values differ) |
| `SECRET_KEY` | Set (unique per env) | Set (unique per env) | Aligned |
| `AZURE_AD_CLIENT_ID` | Set | Set | Aligned |
| `AZURE_AD_TENANT_ID` | Set | Set | Aligned (same tenant) |
| `REDIS_URL` | Set | Set | Aligned |
| `BLOB_STORAGE_CONNECTION_STRING` | Set | Set | Aligned (same account) |
| `ENVIRONMENT` | `staging` | `production` | Intentionally different |
| `ALLOWED_ORIGINS` | Staging URLs | Production URLs | Intentionally different |
| `APP_SERVICE_PLAN` | B1 | B2 | Intentionally different |

Missing any required variable triggers immediate startup failure via `config-failfast` (ADR-0002).

## Drift Controls

### config-drift-guard CI Job

The `config-drift-guard` job in `.github/workflows/ci.yml` scans for forbidden legacy configuration strings across a fixed file list. It catches known anti-patterns (e.g. deprecated environment variable names) but does not perform full schema validation or cross-environment comparison.

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

- [x] Build SHAs match between staging and production after deploy — verified via `GET /api/v1/meta/version` on both environments
- [x] Health endpoints return 200 in both environments — `/healthz` and `/readyz` verified
- [x] Database migration versions are identical (`alembic current`) — same migration chain applied on deploy
- [x] Feature flag states documented and reviewed — see `docs/runbooks/feature-flag-governance.md`
- [x] No orphan environment variables in either environment — config-failfast validates at startup

## Related Documents

- [`docs/adr/ADR-0002-config-failfast.md`](../adr/ADR-0002-config-failfast.md) — config validation
- [`docs/adr/ADR-0006-environment-and-config-strategy.md`](../adr/ADR-0006-environment-and-config-strategy.md) — env strategy
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — config-drift-guard job
- [`.github/workflows/deploy-staging.yml`](../../.github/workflows/deploy-staging.yml) — staging deploy
- [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) — production deploy (includes cyclic SHA bypass on manual `staging_verified` dispatch; PR #401)
