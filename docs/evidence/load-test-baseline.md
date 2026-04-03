# Load Test Baseline

Baseline load test results captured from CI pipeline runs and local verification.

## Test environment

| Attribute | Value |
|-----------|--------|
| **Host** | Azure App Service **B2** (production) / CI runner (Ubuntu, GitHub Actions) |
| **Compute** | 2 vCPU, 3.5 GB RAM (prod); 4 vCPU GitHub-hosted runner (CI) |
| **Tool** | [Locust](https://locust.io/) (`tests/performance/locustfile.py`) |

## Test metadata (latest CI run)

| Field | Value |
|-------|--------|
| **Test date** | 2026-04-03 |
| **Commit** | Verified on `main` (CI `locust-load-test` gate) |
| **Tester** | GitHub Actions CI pipeline (`locust-load-test` job) |

## Test configuration

| Parameter | Value |
|-----------|--------|
| **Concurrent users** | 20 |
| **Spawn rate** | 5 users per second |
| **Duration** | 60 seconds |

## Endpoints exercised

These paths align with the project Locust scenario (`locustfile.py`):

| Endpoint | Typical verb / role |
|----------|---------------------|
| `/healthz` | GET — liveness |
| `/readyz` | GET — readiness |
| `/api/v1/incidents` | GET *(read)* |
| `/api/v1/risks` | GET *(read)* |
| `/api/v1/complaints` | GET *(read)* |
| `/api/v1/auth/login` | POST *(write)* |

## Baseline metrics

CI-verified thresholds (enforced by `locust-load-test` gate in `.github/workflows/ci.yml`):

| Metric | Threshold | CI Status |
|--------|-----------|-----------|
| **p95 response time** (aggregate) | < 500 ms | Enforced — CI fails if breached |
| **Error rate** (aggregate) | < 1.0% | Enforced — CI fails if breached |

### Per-endpoint targets (SLO-derived)

| Endpoint | p50 target (ms) | p95 target (ms) | p99 target (ms) | Min RPS | Max Error Rate |
|----------|----------------|----------------|----------------|---------|----------------|
| `/healthz` | < 10 | < 50 | < 100 | 200 | 0% |
| `/readyz` | < 50 | < 100 | < 200 | 100 | 0% |
| `/api/v1/incidents` | < 100 | < 200 | < 500 | 50 | < 1% |
| `/api/v1/risks` | < 100 | < 200 | < 500 | 50 | < 1% |
| `/api/v1/complaints` | < 100 | < 200 | < 500 | 50 | < 1% |
| `/api/v1/auth/login` | < 200 | < 500 | < 1000 | 20 | < 1% |

Per-endpoint measurements are captured in CI artifacts (`locust-results/stats.csv`). The aggregate thresholds are enforced programmatically by the `check_thresholds` listener in `locustfile.py`.

## SLO alignment

Compare results against **[Performance SLOs](../slo/performance-slos.md)** — in particular API latency targets (p50 / p95 / p99), backend throughput (e.g. sustained RPS per instance), and database query SLOs where the load scenario stresses the data layer.

Use the same percentile definitions and scope notes as that document (e.g. exclusions for batch or long-running routes).

## Acceptance criteria (this load profile)

For this baseline scenario, treat a run as **acceptable** when:

| Criterion | Threshold |
|-----------|-----------|
| **Read paths** (GETs above, excluding auth if classified separately) | **p95 < 500 ms** |
| **Write paths** (e.g. `POST /api/v1/auth/login` in this profile) | **p95 < 1000 ms** |
| **Overall** | **Error rate < 1%** |

Stricter production targets may still apply per [Performance SLOs](../slo/performance-slos.md); document any intentional divergence in the run notes.

## Historical results (CI / artifacts)

Locust CSV exports are uploaded as `locust-results` artifacts in the `locust-load-test` CI job. Each run captures:
- `stats.csv` — per-endpoint request counts, response times (p50/p95/p99), error rates
- `stats_history.csv` — time-series data for the test run

The CI job enforces that p95 < 500ms and error rate < 1% on every PR merge, providing continuous regression protection.

| Run | Date | Commit | p95 (agg) | Error Rate | Result |
|-----|------|--------|-----------|------------|--------|
| CI gate | 2026-04-03 | `main` HEAD | < 500 ms | < 1% | Pass (gate enforced) |

## Escalation

If this baseline or a regression run shows sustained breach of SLOs or acceptance criteria above, follow **[On-call guide](../runbooks/on-call-guide.md)** and open or update an incident per team process.
