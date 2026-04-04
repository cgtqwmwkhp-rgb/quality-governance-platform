# API Service Level Objectives

| Endpoint Category | p50 Target | p95 Target | p99 Target | Error Rate |
|-------------------|-----------|-----------|-----------|------------|
| Health checks (`/healthz`, `/readyz`) | < 50ms | < 100ms | < 200ms | < 0.1% |
| Read operations (GET list/detail) | < 100ms | < 200ms | < 500ms | < 0.5% |
| Write operations (POST/PUT/PATCH) | < 200ms | < 500ms | < 1000ms | < 1.0% |
| File upload/download | < 500ms | < 2000ms | < 5000ms | < 1.0% |
| Search/analytics | < 200ms | < 500ms | < 1500ms | < 0.5% |

## CI vs Production Thresholds
- **CI (Locust):** p95 < 500ms — relaxed for runner hardware variability
- **Production SLO:** p95 < 200ms — target for real-world performance
- The gap is documented in ADR-0012.

**Last updated:** 2026-04-03
