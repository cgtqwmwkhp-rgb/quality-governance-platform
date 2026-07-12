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
- **Artifacts:** `locust-soft-gate-staging` (CSV + markdown/JSON summary + trend + posture)
- **Step summary:** Dedicated **Publish soft-gate trend to job summary** step mirrors the
  markdown report and embeds the trend JSON in the Actions UI

## Trend artifact (Preferred S14)

Each soft-gate run also writes `locust-soft-gate-trend.json` (schema
`locust-soft-gate-trend/v1`) next to the summary files. The record captures:

| Field group | Contents |
|-------------|----------|
| `recorded_at` | UTC timestamp |
| `github.*` | `run_id`, `sha`, `ref`, `workflow` (when present in CI) |
| `result.*` | profile, overall PASS/BREACH, p95, error rate, limits, breaches |

Use successive artifact downloads to compare Preferred staging-bar drift before
promoting the soft-gate to a hard gate. The workflow does **not** invent secrets;
trend fields only reuse public GitHub Actions context env vars.

## Soft-gate dashboard note

Treat each soft-gate workflow run’s **job summary** + `locust-soft-gate-trend.json`
artifact as the Preferred S14 operator dashboard: PASS/BREACH, p95, error rate,
and cross-run drift — still advisory (`continue-on-error` + soft exit). For when
repeated breaches should prompt capacity scale-out (without blocking merges), see
[`queue-depth-scale-hint.md`](queue-depth-scale-hint.md).

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

Use `evaluate_hard_gate_promotion_readiness()` in
`tests/performance/thresholds.py` (schema `locust-soft-gate-hard-gate-ready/v1`)
on successive trend records: ready when the last
`SOFT_GATE_HARD_GATE_PROMOTE["stable_run_count"]` (**5**) runs stay ≤ staging
bar **and** p95 stays ≤ **80%** of the staging limit (400 ms). Advisory only —
it never flips workflow YAML or branch protection.

## Soft-gate re-enable (demote safety valve)

If a hard gate was promoted and staging-bar breaches return, use
`evaluate_soft_gate_reenable_readiness()` (schema `locust-soft-gate-reenable/v1`):
ready when the last `SOFT_GATE_REENABLE["breach_run_count"]` (**2**) runs all
exceed the staging p95 **or** error-rate bar. Advisory only — operators may then
re-set `LOCUST_SOFT_GATE=1` and drop hard-gate branch protection; the helper
never flips workflow YAML.

## Soft-gate posture (operator aggregate)

Use `evaluate_soft_gate_posture()` (schema `locust-soft-gate-posture/v1`) to
collapse scale / re-enable / promote / trial helpers into one
`recommended_posture` (`scale_investigate` → `reenable_soft_gate` →
`promote_hard_gate` → `trial_tighten` → `observe`). Advisory only — see
[`queue-depth-scale-hint.md`](queue-depth-scale-hint.md).

Each soft-gate summary write also emits **`locust-soft-gate-posture.json`** next
to the trend artifact and appends a **Soft-gate posture advisor** section to the
markdown / job summary (including a compact **Signals** line for
scale / reenable / promote / trial). The workflow **Publish soft-gate trend to
job summary** step also mirrors the posture JSON into `$GITHUB_STEP_SUMMARY`
alongside the trend record. Optional prior runs: set `LOCUST_TREND_HISTORY` to a
JSON array or JSONL of `locust-soft-gate-trend/v1` records so the advisor
aggregates history + the current run. Missing history → single-run posture
(usually `observe`). Never invents runs; never flips exit codes / YAML.

## Related

- [`docs/performance/api-slos.md`](api-slos.md) — CI vs production latency tiers
- [`docs/performance/queue-depth-scale-hint.md`](queue-depth-scale-hint.md) — advisory scale-out + non-blocking p95 tighten
- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — load-test pass/fail criteria
- [`tests/performance/locustfile.py`](../../tests/performance/locustfile.py) — profiles + soft-gate listener
- `tests/performance/thresholds.py` — `SOFT_GATE_HARD_GATE_PROMOTE`,
  `evaluate_hard_gate_promotion_readiness()`, `SOFT_GATE_REENABLE`,
  `evaluate_soft_gate_reenable_readiness()`, `evaluate_soft_gate_posture()`
