# API Service Level Objectives

| Endpoint Category | p50 Target | p95 Target | p99 Target | Error Rate |
|-------------------|-----------|-----------|-----------|------------|
| Health checks (`/healthz`, `/readyz`) | < 50ms | < 100ms | < 200ms | < 0.1% |
| Read operations (GET list/detail) | < 100ms | < 200ms | < 500ms | < 0.5% |
| Write operations (POST/PUT/PATCH) | < 200ms | < 500ms | < 1000ms | < 1.0% |
| File upload/download | < 500ms | < 2000ms | < 5000ms | < 1.0% |
| Search/analytics | < 200ms | < 500ms | < 1500ms | < 0.5% |

## CI vs Production Thresholds
- **CI Locust smoke (`LOCUST_PROFILE=ci`):** p95 ≤ 10000ms / error ≤ 3% — relaxed for runner noise (blocking `locust-load-test`)
- **Staging soft-gate (`LOCUST_PROFILE=staging`):** p95 ≤ 500ms / error ≤ 1% — Preferred S14 bar; non-blocking (see [`locust-soft-gate.md`](locust-soft-gate.md))
- **Production SLO:** p95 < 200ms — target for real-world performance
- The gap is documented in ADR-0012.

**Last updated:** 2026-07-11
