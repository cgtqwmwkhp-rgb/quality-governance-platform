# Change Ledger (CL-SAFETY-INSIGHTS-ANALYST-W1)

## Summary
- World-leading Safety Insights Analyst: persisted async deep-runs, Gemini micro-themes with citation validation, Claude synthesis (fail-soft), deterministic dimensions, NM:I ratios, and non-silo feeds into H&S KPIs, executive dashboard, Audit Builder, and case deep-links.

## Change Ledger

| ID | Change | Risk | Mitigation |
|----|--------|------|------------|
| SI-01 | New tables `safety_insight_*` + Alembic `20260815_safety_insights` | Medium | Migration only adds tables; downgrade drops them |
| SI-02 | `POST/GET /api/v1/safety-insights/*` + Celery task | Medium | Tenant-scoped; Gemini required for clustering; fail-soft Claude/Perplexity |
| SI-03 | FE `/analytics/safety-insights` + AI Intelligence redirect | Low | New page; legacy route redirects |
| SI-04 | HS KPI NM:Injury ratios + exec `safety_insights` block | Low | Additive JSON fields |
| SI-05 | Audit Builder `gather_brief` merges latest themes | Low | Fail-closed append |
| SI-06 | Incident list `ids=` filter for theme deep-links | Low | Optional query |
| SI-W3-C1 | Training/competence correlation → `ratios.training_signals` | Low | Honest-empty when sparse; no schema migration |
| SI-W3-C2 | Celery beat `monthly-safety-insights-digest` org-wide deep-run | Medium | Fail-closed per tenant; env disable flag |

## Acceptance criteria
- [x] Deep-run persists themes with validated case citations only
- [x] UI shows micro-themes, dimensions, ratios, synthesis/research honesty
- [x] HS Performance shows NM:Injury ratios
- [x] Latest themes available on executive dashboard payload
- [x] Audit Builder can consume Safety Insight themes
- [x] Unit + vitest + Playwright mocked CUJ

## Test plan
- [x] `pytest tests/unit/test_safety_insights_analyst.py`
- [x] `npm run i18n:check` (en/cy keys)
- [x] Vitest SafetyInsightsAnalyst payload
- [x] Playwright `safety-insights-analyst.spec.ts` (mocked)
- [ ] Post-deploy: migration applied; Gemini key present; optional Anthropic/Perplexity

## Gate 0
- [x] Scope lock + AC defined + Change Ledger complete
