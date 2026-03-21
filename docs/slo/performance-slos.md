# Performance SLOs (D04)

Service level objectives for latency, throughput, frontend experience, and bundle size for the Quality Governance Platform. These targets apply to **production** unless a scenario explicitly states otherwise.

---

## API latency SLOs

**Scope:** Standard CRUD HTTP handlers (GET/POST/PATCH/PUT/DELETE) on stable, non-batch API routes under normal load.

| Percentile | Target |
|------------|--------|
| p50 | < 100 ms |
| p95 | < 200 ms |
| p99 | < 500 ms |

**Notes:** Batch exports, report generation, and explicitly documented long-running operations may use separate SLOs documented on those endpoints.

---

## Database query SLOs

| Class | Percentile | Target |
|-------|------------|--------|
| Indexed lookups and simple filters | p95 | < 50 ms |
| Complex joins / aggregations (documented query paths) | p99 | < 200 ms |

**Notes:** Use appropriate indexes and query plans; breach investigations should include `EXPLAIN` and slow-query logs.

---

## Frontend performance budget

| Metric | SLO target | CI reference |
|--------|------------|----------------|
| First Contentful Paint (FCP) | < 1.5 s | [`frontend/lighthouserc.json`](../../frontend/lighthouserc.json) — `first-contentful-paint` (currently warn at 2000 ms; **tighten toward 1500 ms** to match this SLO) |
| Largest Contentful Paint (LCP) | < 2.5 s | Same file — `largest-contentful-paint` (currently warn at 3000 ms; **tighten toward 2500 ms** to match this SLO) |
| Total Blocking Time (TBT) | < 200 ms | Same file — `total-blocking-time` (currently error at 500 ms; **tighten toward 200 ms** to match this SLO) |
| Cumulative Layout Shift (CLS) | < 0.1 | Same file — `cumulative-layout-shift` (error at 0.1; **aligned** with this SLO) |

Lighthouse runs against the built app (`staticDistDir: ./dist`, `url` in that config). Treat lab metrics as regression gates; supplement with Real User Monitoring where available.

---

## Bundle size budget

| Budget | SLO target | CI reference |
|--------|------------|----------------|
| Main application JS (gzip) | < 300 KB | [`frontend/.size-limit.json`](../../frontend/.size-limit.json) — `dist/assets/index-*.js` (currently **350 kB** gzip; **reduce to ≤ 300 kB** to meet SLO) |
| Total initial JS load (gzip) | < 500 KB | Same file — sum of entry + critical chunks counted toward first navigation (today: `index-*.js` + `vendor-*.js` at **350 kB** + **250 kB** per-file caps; **align combined budget to ≤ 500 kB** and per-chunk caps as needed) |

CSS and other assets remain subject to existing limits in `.size-limit.json` unless superseded by a dedicated doc.

---

## Backend throughput

- **Sustain** at least **100 requests per second** per application instance under the standard load profile (see load tests below).
- While at or above that throughput, **p99 API latency** must remain **< 500 ms** for routes in scope of the API latency SLOs (excluding documented long-running operations).

---

## Measurement and alerting

### Metric collection (OpenTelemetry)

| Signal | Name | Use |
|--------|------|-----|
| Histogram / summary | `api.response_time_ms` | End-to-end HTTP request duration per route/method; drives p50/p95/p99 for API SLOs |
| Histogram / summary | `db.query_time_ms` | Per-statement or per-repository query duration; tag with `query.class` = `indexed` vs `complex_join` where practical |

**Attributes (recommended):** `http.route`, `http.method`, `service.name`, `deployment.environment`, and for DB spans `db.system`, `db.operation`.

### Alert thresholds (starting points)

| Area | Condition | Severity |
|------|-----------|----------|
| API CRUD | p95 > 200 ms **or** p99 > 500 ms for 15+ minutes | Page / high priority |
| API CRUD | p50 > 100 ms sustained 1 h | Warning / ticket |
| DB indexed | p95 > 50 ms for 15+ minutes | Warning |
| DB complex | p99 > 200 ms for 15+ minutes | Warning |
| Throughput | Sustained load ≥ 100 req/s/instance **and** p99 ≥ 500 ms | Page |
| Frontend | Lighthouse CI or RUM: LCP, FCP, TBT, or CLS SLO breach in release channel | Block release or rollback per policy |

Tune windows and burn rates to match error budget policy in `docs/slo.yaml`.

---

## Load test baselines

**Reference:** [`tests/performance/locustfile.py`](../../tests/performance/locustfile.py)

### How to run (example)

```bash
locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
  --headless -u 100 -r 10 --run-time 5m
```

### Pass / fail criteria

| Criterion | Pass |
|-----------|------|
| **p95 response time** | ≤ **500 ms** (enforced in `PERF_THRESHOLDS` in the locustfile; stricter **200 ms** p95 applies to **CRUD SLO** above — use extended reports or tagged routes to assert CRUD separately when tooling allows) |
| **Error rate** | ≤ **1.0%** (as in `PERF_THRESHOLDS["error_rate_pct"]`) |
| **Throughput** | ≥ **100 req/s** aggregate **or** per-instance target met in the deployment under test (document instance count in the run artifact) |
| **p99 latency** | **< 500 ms** for in-scope routes while at target throughput (aligns with backend throughput SLO; add percentile checks in CI when Locust stats are exported) |

A non-zero exit code from the locustfile threshold hook indicates **fail**. Save Locust HTML/CSV reports with release artifacts for regression comparison.

---

## Performance review cadence

| Cadence | Activity |
|---------|----------|
| **Weekly** | Review **p99** API and DB metrics (and key frontend vitals if RUM available); confirm no sustained regression vs prior week |
| **Monthly** | **Trend analysis** — error budgets, percentile drift, bundle size and Lighthouse trends, load-test baselines; propose config or code changes |

---

## Related documents

- [`docs/slo.yaml`](../../docs/slo.yaml) — machine-oriented SLO summary including `performance` section
- [`frontend/lighthouserc.json`](../../frontend/lighthouserc.json)
- [`frontend/.size-limit.json`](../../frontend/.size-limit.json)
- [`tests/performance/locustfile.py`](../../tests/performance/locustfile.py)
