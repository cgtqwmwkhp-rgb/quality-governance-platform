# Capacity Plan (D25)

Current and target capacity for the Quality Governance Platform.

## Compute Capacity

| Resource | Current Config | Min Instances | Max Instances | Scale Trigger |
|----------|---------------|---------------|---------------|---------------|
| App Service (Prod) | B2 (2 vCPU, 3.5 GB) | 2 | 6 | CPU > 70% for 5 min |
| App Service (Staging) | B1 (1 vCPU, 1.75 GB) | 1 | 1 | N/A |

**Evidence**: `scripts/infra/autoscale-settings.json`

## Database Capacity

| Metric | Current | Threshold | Action |
|--------|---------|-----------|--------|
| PostgreSQL SKU | Burstable B1ms (matches [`cost-controls.md`](cost-controls.md) inventory) | N/A | Right-size quarterly |
| Storage | 32 GB provisioned | 80% (25.6 GB) | Extend or archive |
| Connections | Pool 10 + overflow 20 | 80% pool usage | Increase pool_size |
| Statement timeout | 30s | N/A | Enforce via `database.py` |

**Evidence**: `src/infrastructure/database.py` (pool config, timeout)

## Throughput Targets

| Metric | Target | Evidence |
|--------|--------|----------|
| API throughput (per instance) | >= 100 req/s | `docs/slo/performance-slos.md` |
| API p95 latency | < 200ms | `docs/slo/performance-slos.md` |
| API p99 latency | < 500ms | `docs/slo/performance-slos.md` |
| Concurrent users (current load) | < 100 | Platform usage baseline |

## Load Testing

Load tests are run via Locust (`tests/performance/locustfile.py`) with the following profile:
- 20 concurrent users, 5/s spawn rate, 60s duration
- Endpoints: `/healthz`, `/readyz`, `/api/v1/incidents`, `/api/v1/risks`, `/api/v1/complaints`, `/api/v1/auth/login`

Results are captured in `docs/evidence/load-test-baseline.md` and as CI artifacts.

## Growth Projections

| Horizon | Expected Users | Expected Tenants | Capacity Action |
|---------|---------------|------------------|-----------------|
| Current | < 100 | 1-5 | B2 with autoscale (2-6) |
| 6 months | 100-500 | 5-20 | Evaluate S1 SKU, increase DB to B2ms |
| 12 months | 500-2000 | 20-50 | S2/P1v3, dedicated PostgreSQL, Redis Premium |

## Related Documents

- [`docs/infra/cost-controls.md`](cost-controls.md) — cost optimization
- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — performance SLOs
- [`docs/evidence/load-test-baseline.md`](../evidence/load-test-baseline.md) — load test results
- [`scripts/infra/autoscale-settings.json`](../../scripts/infra/autoscale-settings.json) — autoscale config
