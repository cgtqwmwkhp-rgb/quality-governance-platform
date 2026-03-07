# ADR-0003: Readiness Probe Database Check

**Status**: Accepted
**Date**: 2026-01-25
**Decision Makers**: Platform Engineering Team

## Context

Container orchestrators (Azure Container Apps, Kubernetes) use readiness probes to determine whether a container should receive traffic. A liveness-only probe (`/healthz`) confirms the process is alive but does not verify that the application can actually serve requests, which requires database connectivity.

## Decision

Implement a separate readiness endpoint (`GET /readyz`) that performs a lightweight database connectivity check (`SELECT 1`) before reporting ready status.

- **`/healthz`** (liveness): Returns 200 if the Python process is running. No dependency checks. Used by orchestrator to decide whether to restart the container.
- **`/readyz`** (readiness): Returns 200 if the application is running AND the database is reachable. Returns 503 with diagnostic details if database is unavailable. Used by load balancer to decide whether to route traffic.

Both endpoints include `request_id` in their response for correlation.

## Consequences

- **Positive**: Traffic is never routed to instances with broken database connections; deployment health checks verify end-to-end readiness; 503 response includes diagnostic information for faster incident resolution.
- **Negative**: Readiness probe adds one `SELECT 1` query per probe interval (default 30s); brief database maintenance windows cause traffic draining (by design).
- **Mitigations**: Pool pre-ping (`pool_pre_ping=True`) on the async engine ensures stale connections are detected and replaced; readiness check uses a short timeout to avoid blocking.

## References

- `src/main.py` — `readiness_check()` endpoint
- `Dockerfile` — `HEALTHCHECK` uses `/healthz` (liveness)
- `.github/workflows/deploy-production.yml` — readiness-first health check with exponential backoff
