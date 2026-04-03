# ADR-0012: Infrastructure Platform Choices

**Status**: Accepted
**Date**: 2026-04-03
**Deciders**: Platform Engineering Team

## Context

QGP requires a hosting platform, database, caching layer, and CI/CD pipeline. The target audience is UK-based public sector and transport organizations.

## Decisions

### Hosting: Azure App Service (Linux)
- **SKU**: B1 (staging), B2 (production) — £45-75/month
- **Region**: UK South (data sovereignty, lowest latency for UK users)
- **Rationale**: PaaS reduces operational burden vs IaaS/K8s. Azure alignment with UK Gov G-Cloud.

### Database: Azure Database for PostgreSQL — Flexible Server
- **SKU**: Burstable B1ms (1 vCore, 2 GB RAM)
- **Rationale**: Cost-effective for <2000 users. Automated backups, PITR, HA options.

### Cache: Azure Cache for Redis — Basic C0
- **Rationale**: Minimal footprint for session/idempotency/rate-limiting. Upgrade path to Standard C1 if needed.

### Static Frontend: Azure Static Web Apps
- **Rationale**: Free tier, global CDN, integrated auth, CI/CD via GitHub Actions.

### CI/CD: GitHub Actions
- **Rationale**: Native GitHub integration, extensive marketplace, matrix builds, caching.

### Key Vault: Azure Key Vault
- **Rationale**: Centralized secret management, audit logging, HSM-backed keys.

## Alternatives Considered

| Decision | Alternative | Why Not |
|---|---|---|
| App Service | AKS | Over-engineering for team size; higher ops burden |
| App Service | AWS ECS | Azure alignment with UK Gov procurement |
| PostgreSQL | CosmosDB | Relational model better fits domain; cost |
| Redis Basic | Redis Enterprise | Overkill for current scale |

## Consequences

- Azure lock-in accepted (mitigated by Docker containers + standard Postgres)
- B1/B2 scaling limit ~200 concurrent connections (plan upgrade to S1 at 2000+ users)
- Redis Basic has no persistence — acceptable for cache/ephemeral data
