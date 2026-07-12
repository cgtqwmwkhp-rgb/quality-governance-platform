# Queue-depth scale hint (Preferred S14)

Advisory guidance for when soft-gate staging-bar breaches should trigger
**capacity investigation / scale-out**, without blocking merges.

This is documentation + constants only. It does **not** change Locust exit
codes, branch protection, or App Service autoscale settings.

## Why this exists

Preferred S14 measures the staging load shape (20 users / 5 spawn / 60s) via the
non-blocking soft-gate. When p95 or error rate breaches repeatedly, operators
need a shared rule of thumb for *when* to scale compute vs *when* to keep
observing under soft-gate.

## Soft-gate dashboard (where to look)

Use the GitHub Actions soft-gate run as the Preferred S14 “dashboard”:

1. Open the **Locust Soft-Gate (Staging Profile)** workflow run.
2. Read the job summary (**Publish soft-gate trend to job summary**): PASS/BREACH,
   p95, error rate, and embedded `locust-soft-gate-trend.json`.
3. Download artifact `locust-soft-gate-staging` and compare successive
   `locust-soft-gate-trend.json` records (schema `locust-soft-gate-trend/v1`).

No separate product UI is required for this score-mover; the Actions summary +
trend artifact are the operator surface.

## Queue-depth / concurrency scale hints

Map soft-gate pressure to the capacity plan (`docs/infra/capacity-plan.md`)
using these **advisory** ratios (also in
`tests/performance/thresholds.py` as `QUEUE_DEPTH_SCALE_HINTS`):

| Signal | Hint threshold | Operator action |
|--------|----------------|-----------------|
| Soft-gate p95 | Sustained **> 1.5×** staging limit (500 ms → **> 750 ms**) across **≥ 3** recent main/PR soft-gate runs | Investigate app/DB hotspots; consider App Service scale-out (CPU > 70% for 5 min already in capacity plan) |
| Soft-gate error rate | Sustained **> 2×** staging limit (1% → **> 2%**) across **≥ 3** runs | Check dependency/DB pool saturation before raising instance count |
| Concurrent users vs plan | Soft-gate shape is **20** users; platform baseline target is **< 100** concurrent | If production concurrent users approach **~50%** of growth-band (or soft-gate breaches while prod traffic rises), schedule scale evaluation per capacity plan horizons |

These hints are **non-blocking**: they never fail CI. Record decisions in the
usual ops/evidence trail when acting on them.

## Non-blocking p95 tighten (later)

Staging soft-gate keeps p95 ≤ **500 ms** (Preferred bar). Production SLO remains
p95 **< 200 ms**. Tightening is intentional and staged:

1. **Observe** — collect soft-gate trend artifacts until p95 is stably under 500 ms
   on GHA runners (low false-positive rate).
2. **Document** — note candidate tighter soft-gate override (e.g. trial
   `LOCUST_P95_MS=350`) in a follow-up PR under this allowlist only; keep
   `LOCUST_SOFT_GATE=1` so merges stay green.
3. **Promote** — only after evidence, drop soft-gate / require the check (see
   hard-gate promotion in [`locust-soft-gate.md`](locust-soft-gate.md)).

Do **not** tighten the blocking `ci` profile (`LOCUST_P95_MS=10000`) as a
Preferred score-mover; that profile exists for runner-noise tolerance.

## Related

- [`locust-soft-gate.md`](locust-soft-gate.md) — soft-gate workflow + trend artifact
- [`api-slos.md`](api-slos.md) — CI vs staging vs production latency tiers
- [`docs/infra/capacity-plan.md`](../infra/capacity-plan.md) — autoscale triggers
- `tests/performance/thresholds.py` — `QUEUE_DEPTH_SCALE_HINTS` constants
