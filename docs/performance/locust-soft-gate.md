# Locust soft-gate (Preferred S14 staging profile)

Path-to-Preferred score-mover for **S14 Performance** (6.4 → 8.5): evaluate the
staging load-test bar on every PR **without blocking merge**.

## Why soft-gate

The blocking CI Locust job (`locust-load-test` in `ci.yml`) uses a **relaxed CI
profile** (`LOCUST_P95_MS=10000`, error ≤ 3%) so noisy GitHub-hosted runners do
not fail merges. That leaves the Preferred staging bar unmeasured.

The soft-gate workflow runs the **staging profile** thresholds and reports
breaches clearly, then exits successfully so the Preferred bar is visible before
we promote to a hard gate.

## Staging profile (thresholds)

| Criterion | Soft-gate limit | Source |
|-----------|-----------------|--------|
| Concurrent users | 20 | `docs/infra/capacity-plan.md` |
| Spawn rate | 5 / s | capacity plan / CI Locust shape |
| Run time | 60 s | capacity plan / CI Locust shape |
| p95 response time | ≤ **500 ms** | load-test SLO / `PERF_THRESHOLDS` |
| Error rate | ≤ **1.0%** | load-test SLO / `PERF_THRESHOLDS` |

Env controls (see `tests/performance/locustfile.py`):

| Variable | Purpose |
|----------|---------|
| `LOCUST_PROFILE=staging` | Select staging thresholds + documented load shape metadata |
| `LOCUST_SOFT_GATE=1` | Report breaches; keep process exit code 0 |
| `LOCUST_P95_MS` / `LOCUST_ERROR_RATE_PCT` | Optional overrides (win over profile) |
| `LOCUST_SUMMARY_DIR` | Where `locust-soft-gate-summary.{md,json}` are written |

## Workflow

- **File:** [`.github/workflows/locust-soft-gate.yml`](../../.github/workflows/locust-soft-gate.yml)
- **Triggers:** `pull_request`, `push` to `main`, `workflow_dispatch`
- **Merge impact:** non-blocking (`continue-on-error: true` + soft exit)
- **Artifacts:** `locust-soft-gate-staging` (CSV + markdown/JSON summary)
- **Step summary:** GitHub Actions job summary mirrors the markdown report

## Local run

```bash
# Start the API locally, then:
LOCUST_PROFILE=staging LOCUST_SOFT_GATE=1 LOCUST_SUMMARY_DIR=./locust-soft-gate-out \
  locust -f tests/performance/locustfile.py \
    --host http://127.0.0.1:8000 \
    --users 20 --spawn-rate 5 \
    --run-time 60s --headless --only-summary
```

## Hard-gate promotion (later)

When staging/CI p95 is stable under the staging profile:

1. Drop `LOCUST_SOFT_GATE` (or set `0`) in the soft-gate workflow **or** tighten
   `locust-load-test` to `LOCUST_PROFILE=staging` without soft-gate.
2. Require the check in branch protection / `all-checks` only after evidence
   shows low false-positive rate on GHA runners.
3. Keep the relaxed `ci` profile available for smoke-only runs if needed.

## Related

- [`docs/performance/api-slos.md`](api-slos.md) — CI vs production latency tiers
- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — load-test pass/fail criteria
- [`tests/performance/locustfile.py`](../../tests/performance/locustfile.py) — profiles + soft-gate listener
