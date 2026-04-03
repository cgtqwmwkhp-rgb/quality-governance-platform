# Load test baseline (evidence template)

This document captures baseline load test results for regression comparison. **Populate metrics after each run**; the table below is a template until measured values are filled in.

## Test environment

| Attribute | Value |
|-----------|--------|
| **Host** | Azure App Service **B2** |
| **Compute** | 2 vCPU, 3.5 GB RAM |
| **Tool** | [Locust](https://locust.io/) |

## Test metadata (per run)

| Field | Value |
|-------|--------|
| **Test date** | `2026-03-20` *(template — update after each run)* |
| **Commit / image** | *(e.g. git SHA or container digest)* |
| **Tester** | *(name or automation job ID)* |

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

Targets derived from [Performance SLOs](../slo/performance-slos.md). Values below represent acceptance thresholds; actual measurements are recorded per-run in CI artifacts.

| Endpoint | p50 target (ms) | p95 target (ms) | p99 target (ms) | Min RPS | Max Error Rate |
|----------|----------------|----------------|----------------|---------|----------------|
| `/healthz` | < 10 | < 50 | < 100 | 200 | 0% |
| `/readyz` | < 50 | < 100 | < 200 | 100 | 0% |
| `/api/v1/incidents` | < 100 | < 200 | < 500 | 50 | < 1% |
| `/api/v1/risks` | < 100 | < 200 | < 500 | 50 | < 1% |
| `/api/v1/complaints` | < 100 | < 200 | < 500 | 50 | < 1% |
| `/api/v1/auth/login` | < 200 | < 500 | < 1000 | 20 | < 1% |

*RPS* = mean requests per second for that endpoint during the steady window; *error rate* = failed requests / total for that endpoint (or tool-reported aggregate, noted in run notes).

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

*Placeholder for automation:* append or link tables generated from **Locust CSV exports** (e.g. `locust-results` artifacts from CI). Recommended columns: run ID, date, commit, environment, and the same per-endpoint percentiles and error rate as above.

```text
<!-- Example: link or embed CI artifact path, e.g. build job → locust-results/stats.csv -->
```

## Escalation

If this baseline or a regression run shows sustained breach of SLOs or acceptance criteria above, follow **[On-call guide](../runbooks/on-call-guide.md)** and open or update an incident per team process.
