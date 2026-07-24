# Change Ledger (CL-SAFETY-INSIGHTS-ANALYST)

## Summary
- World-leading Safety Insights Analyst (Waves 1–3): persisted async deep-runs, Gemini micro-themes with citation validation, Claude synthesis (fail-soft), deterministic dimensions, NM:I ratios, board-pack PDF, training signals, monthly digest, and non-silo feeds into H&S KPIs, executive dashboard, Audit Builder, case deep-links; Advanced Analytics demo theatre retired.

## Change Ledger

| ID | Change | Risk | Mitigation |
|----|--------|------|------------|
| SI-01 | New tables `safety_insight_*` + Alembic `20260815_safety_insights` | Medium | Migration only adds tables; downgrade drops them |
| SI-02 | `POST/GET /api/v1/safety-insights/*` + Celery task | Medium | Tenant-scoped; Gemini required for clustering; fail-soft Claude/Perplexity |
| SI-03 | FE `/analytics/safety-insights` + AI Intelligence redirect | Low | New page; legacy route redirects |
| SI-04 | HS KPI NM:Injury ratios + exec `safety_insights` block | Low | Additive JSON fields |
| SI-05 | Audit Builder `gather_brief` merges latest themes | Low | Fail-closed append |
| SI-06 | Incident list `ids=` filter for theme deep-links | Low | Optional query |
| SI-W2-A | Retire Advanced Analytics demo AI Insights/Benchmarks | Low | Deep-link to live analyst |
| SI-W2-B | Board-pack PDF export (fpdf2) | Low | Fail-closed 404/500 |
| SI-W3-C1 | Training/competence correlation → `ratios.training_signals` | Low | Honest-empty when sparse; no schema migration |
| SI-W3-C2 | Celery beat `monthly-safety-insights-digest` | Medium | Fail-closed per tenant; env disable flag |
| SI-W3-D | NM/RTA/Complaint `ids=` list filters + URL sync | Low | Mirrors incident deep-link |

## Acceptance criteria
- [x] Deep-run persists themes with validated case citations only
- [x] UI shows micro-themes, dimensions, ratios, synthesis/research honesty
- [x] HS Performance shows NM:Injury ratios
- [x] Latest themes available on executive dashboard payload
- [x] Audit Builder can consume Safety Insight themes
- [x] Advanced Analytics no longer shows fake benchmarks/insights
- [x] Board-pack PDF export + training signals + monthly digest
- [x] Theme deep-links for Incident/NM/RTA/Complaint
- [x] Unit + vitest + Playwright mocked CUJ

## Test plan
- [x] `pytest tests/unit/test_safety_insights_{analyst,export,training}.py` (20 passed)
- [x] `npm run i18n:check` (en/cy keys)
- [x] Vitest SafetyInsightsAnalyst payload
- [x] Playwright `safety-insights-analyst.spec.ts` (mocked)
- [ ] Post-deploy: migration applied; tip==LIVE; Gemini key; optional Anthropic/Perplexity

## Gate 0
- [x] Scope lock + AC defined + Change Ledger complete
