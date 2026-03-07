# ADR-0002: Production Configuration Fail-Fast

**Status**: Accepted
**Date**: 2026-01-22
**Decision Makers**: Platform Engineering Team

## Context

Running the application in production with development-grade configuration (placeholder secret keys, localhost database URLs, debug mode enabled) creates severe security and reliability risks. These misconfigurations have historically been the root cause of production incidents across the industry.

## Decision

The `Settings` class in `src/core/config.py` performs mandatory validation when `APP_ENV=production`:

1. **SECRET_KEY**: Must not match any known placeholder value (`change-me-in-production`, `__CHANGE_ME__`, etc.)
2. **JWT_SECRET_KEY**: Same placeholder rejection as SECRET_KEY
3. **PSEUDONYMIZATION_PEPPER**: Must not be a placeholder; minimum 16 characters (GDPR requirement)
4. **DATABASE_URL**: Must not contain `localhost` or `127.0.0.1`; must start with `postgresql` or `sqlite`

If any validation fails, the application raises `ValueError` at startup and refuses to boot. This is intentionally a hard crash, not a warning.

## Consequences

- **Positive**: Impossible to run production with unsafe configuration; configuration errors detected at startup rather than at runtime; CI proof via `tests/test_config_failfast.py` and CI job `config-failfast-proof`.
- **Negative**: First-time deployment requires all secrets to be properly configured in Key Vault before the app will start; debugging requires explicit `APP_ENV=development`.
- **Mitigations**: `.env.example` documents all required variables; deployment workflow injects secrets from Azure Key Vault; staging environment validates configuration before production promotion.

## References

- `src/core/config.py` — `_validate_production_settings()` method
- `tests/test_config_failfast.py` — CI proof that validation works
- `.github/workflows/ci.yml` — `config-failfast-proof` job
