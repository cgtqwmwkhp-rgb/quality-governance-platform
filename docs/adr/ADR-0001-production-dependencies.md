# ADR-0001: Production Infrastructure Dependencies

**Status**: Accepted
**Date**: 2026-01-20
**Decision Makers**: Platform Engineering Team

## Context

The Quality Governance Platform requires several infrastructure services in production (PostgreSQL, Redis, Azure Blob Storage, Azure AD). Deployments must validate that all required dependencies are reachable before traffic is routed to a new revision, to prevent partial-availability states that could lead to data loss or degraded user experience.

## Decision

Implement a production dependencies gate (`scripts/governance/prod-dependencies-gate.sh`) that runs as a pre-deployment check in the CI/CD pipeline. This gate validates:

1. **Database connectivity**: PostgreSQL is reachable and responds to queries
2. **Redis availability**: Cache layer is operational (with graceful fallback to in-memory)
3. **Azure Blob Storage**: Storage account is accessible for evidence uploads
4. **Azure AD JWKS**: Authentication provider's public keys are fetchable

The gate runs in both the staging and production deployment workflows and blocks deployment if any critical dependency (database, Azure AD) is unreachable. Non-critical dependencies (Redis, Blob Storage) produce warnings but do not block.

## Consequences

- **Positive**: Zero deployments to environments with broken infrastructure; faster incident detection; explicit dependency documentation.
- **Negative**: Adds ~30 seconds to deployment time; requires infrastructure credentials in CI environment; false positives possible during Azure service maintenance windows.
- **Mitigations**: 3-retry logic with exponential backoff; maintenance window awareness via Azure Service Health API integration (future).

## References

- `scripts/governance/prod-dependencies-gate.sh`
- `.github/workflows/deploy-production.yml` (prod-dependencies-gate job)
- `.github/workflows/deploy-staging.yml` (preflight checks)
