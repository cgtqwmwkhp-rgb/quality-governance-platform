# Performance Budget Evidence (D04)

Evidence of CI-enforced performance gates across frontend and backend.

## Frontend Performance Gates

| Gate | Tool | CI Job | Config File | Threshold |
|------|------|--------|-------------|-----------|
| Bundle size (JS main) | size-limit | `performance-budget` | `frontend/.size-limit.json` | 300 KB gzip |
| Bundle size (vendor) | size-limit | `performance-budget` | `frontend/.size-limit.json` | 220 KB gzip |
| Bundle size (CSS) | size-limit | `performance-budget` | `frontend/.size-limit.json` | 40 KB gzip |
| Lighthouse Performance | @lhci/cli | `performance-budget` | `lighthouserc.json` | >= 0.90 |
| Lighthouse Accessibility | @lhci/cli | `performance-budget` | `lighthouserc.json` | >= 0.95 |
| Lighthouse Best Practices | @lhci/cli | `performance-budget` | `lighthouserc.json` | >= 0.90 |
| LCP | @lhci/cli | `performance-budget` | `lighthouserc.json` | < 2500 ms |
| CLS | @lhci/cli | `performance-budget` | `lighthouserc.json` | < 0.1 |
| TBT | @lhci/cli | `performance-budget` | `lighthouserc.json` | < 300 ms |

## Backend Performance Gates

| Gate | Tool | CI Job | Config File | Threshold |
|------|------|--------|-------------|-----------|
| API p95 latency | Locust | `locust-load-test` | `tests/performance/locustfile.py` | < 500 ms |
| Error rate | Locust | `locust-load-test` | `tests/performance/locustfile.py` | < 1% |

## SLO Alignment

All thresholds align with targets defined in `docs/slo/performance-slos.md`:
- API CRUD p50 < 100ms, p95 < 200ms, p99 < 500ms
- Frontend FCP < 1.5s, LCP < 2.5s, TBT < 200ms, CLS < 0.1
- Bundle size main JS < 300KB gzip
- Sustained throughput >= 100 req/s/instance

## Evidence Artifacts

Performance results are captured as CI workflow artifacts:
- `locust-results` — CSV and HTML reports from Locust load test runs
- Lighthouse reports uploaded to temporary public storage via `@lhci/cli`
- Size-limit output included in `performance-budget` job logs
