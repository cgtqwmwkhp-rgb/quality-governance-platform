# Analytics Baseline — Quality Governance Platform

> Last updated: 2026-03-07

## 1. Current Measurement Capabilities

### Backend Telemetry

| Capability | Status | Implementation |
|-----------|--------|----------------|
| Request logging | Active | FastAPI middleware → structured JSON logs |
| Error tracking | Active | Global exception handler → Azure Monitor |
| Custom metrics | Active | `track_metric()` via `azure_monitor.py` |
| DLQ monitoring | Active | `dlq.size` metric emitted on task failure |
| Circuit breaker | Active | `circuit_breaker.*.state` + `*.transition` metrics |
| Audit trail | Active | Database-backed audit log (all mutations) |
| Performance tracing | Partial | OpenCensus (deprecated) → migration to OpenTelemetry pending |
| SLO/SLI tracking | Documented | `docs/observability/slo-definitions.md` — not yet wired to automated alerts |

### Frontend Telemetry

| Capability | Status | Implementation |
|-----------|--------|----------------|
| Web Vitals | Active | `web-vitals` library → `/api/v1/telemetry/web-vitals` |
| Error tracking | Active | `services/errorTracker.ts` → global listeners |
| Analytics events | Partial | `services/telemetry.ts` exists but disabled in production (CORS) |
| Feature usage | Not tracked | No event instrumentation on user interactions |
| Session recording | Not available | No Hotjar / FullStory / LogRocket integration |

### CI/CD Metrics

| Capability | Status | Implementation |
|-----------|--------|----------------|
| Test coverage | Active | `pytest-cov` (backend, threshold 50%) + `vitest` (frontend) |
| Lighthouse scores | Configured | `lighthouserc.json` with score gates |
| Build time | Partial | GitHub Actions timestamps (not tracked as metric) |
| Bundle size | Active | `size-limit` in `package.json` |
| Security scanning | Active | Bandit, pip-audit, Semgrep, Trivy, Gitleaks, CodeQL |

---

## 2. Recommended KPIs

### Product Health KPIs

| KPI | Target | Measurement Source |
|-----|--------|--------------------|
| **Uptime** | ≥ 99.9% | `/readyz` probe + Azure Monitor |
| **API p95 latency** | ≤ 500ms | Request logs |
| **Error rate** | ≤ 0.1% 5xx | Request logs |
| **LCP** | ≤ 2.5s | Web Vitals |
| **CLS** | ≤ 0.1 | Web Vitals |
| **INP** | ≤ 200ms | Web Vitals |

### Engagement KPIs

| KPI | Target | Measurement Source |
|-----|--------|--------------------|
| **DAU / MAU ratio** | ≥ 40% | Auth token activity |
| **Session duration** | Benchmark TBD | Frontend telemetry (not yet tracked) |
| **Feature adoption** | ≥ 60% active module usage | API request distribution (needs instrumentation) |
| **Task completion rate** | ≥ 90% actions closed within SLA | Actions API + workflow engine |

### Quality KPIs

| KPI | Target | Measurement Source |
|-----|--------|--------------------|
| **Test coverage (backend)** | ≥ 80% | pytest-cov |
| **Test coverage (frontend)** | ≥ 70% | vitest coverage |
| **Lighthouse performance** | ≥ 80 | Lighthouse CI |
| **Lighthouse accessibility** | ≥ 90 | Lighthouse CI |
| **Open DLQ items** | ≤ 5 | DLQ metrics |
| **Dependency vulnerabilities** | 0 critical, ≤ 3 high | pip-audit + npm audit |

### Business Outcomes KPIs

| KPI | Target | Measurement Source |
|-----|--------|--------------------|
| **Incidents resolved within SLA** | ≥ 95% | Workflow engine |
| **Complaints acknowledged < 24h** | ≥ 98% | Complaint model timestamps |
| **Audit completion rate** | ≥ 90% | Audit runs (completed / scheduled) |
| **Risk review compliance** | 100% | Risk `next_review_date` vs current date |
| **Policy review cycle adherence** | ≥ 95% | Policy `next_review_date` |

---

## 3. Instrumentation Gaps

### High Priority

1. **Frontend feature-usage events** — No `trackEvent()` calls on key user actions (create incident, submit audit, escalate risk). Wire `telemetry.ts` to emit events on POST/PUT mutations.
2. **Production telemetry CORS** — `services/telemetry.ts` is disabled in production due to CORS. Configure the backend to accept telemetry POSTs from the frontend origin.
3. **Session duration / page views** — No page-view tracking in the SPA router. Add route-change listener that emits `page_view` events.
4. **SLO alerting** — SLOs are documented but not wired to Azure Monitor alerts. Create alert rules for each SLI threshold.

### Medium Priority

5. **Funnel analysis** — No multi-step funnel tracking (e.g., incident creation → investigation assignment → action completion).
6. **Search analytics** — No tracking of search queries, result counts, or zero-result rates.
7. **Build/deploy metrics** — CI pipeline duration and success rate not tracked as time-series metrics.

### Low Priority

8. **A/B testing infrastructure** — No feature flag integration for controlled rollouts with measurable outcomes.
9. **Cohort analysis** — No tenant-level or role-level segmentation of usage patterns.
10. **Cost attribution** — No per-tenant resource consumption tracking (API calls, storage, compute).

---

## 4. Implementation Roadmap

### Week 1–2: Core Instrumentation

- Fix telemetry CORS to enable production event collection.
- Add `trackEvent()` calls to the top 10 user actions.
- Add route-change page-view tracking.
- Wire SLO thresholds to Azure Monitor alert rules.

### Week 3–4: Dashboard Buildout

- Deploy the 3 Azure Monitor dashboard templates (API Health, Auth/Security, Business Metrics).
- Create a "Product Health" composite dashboard combining Web Vitals + API metrics.
- Set up weekly automated Lighthouse runs in CI with trend tracking.

### Week 5–8: Advanced Analytics

- Implement funnel tracking for the 3 primary user journeys.
- Add search analytics instrumentation.
- Build tenant-level usage reporting for customer success.
- Evaluate session recording tools (LogRocket / FullStory) for UX insights.
