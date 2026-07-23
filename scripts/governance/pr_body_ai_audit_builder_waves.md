# Change Ledger (CL-AI-AUDIT-BUILDER-WAVES)

## Summary
Ship the risk-driven AI Audit Builder: intent wizard → platform/research brief → clarifying Q&A → similar-template gate → generate-from-brief, with near-miss search, live Perplexity (fail-closed), Assist Map suggestions after generate, and case→builder entry points.

## Change Ledger
| Area | Change |
|---|---|
| Orchestrator | `AuditBuilderOrchestrator` gather brief / QA / similar / compose prompt / workforce signals |
| API | `/ai-templates/gather-brief`, `/apply-qa`, `/similar-templates`, `/research`, `/generate-from-brief` |
| Perplexity | Live provider in `library_horizon_adapter` + `research_with_perplexity` (fail-closed) |
| Search | Near misses in `SearchService`; `entity_id` on search results |
| FE | Multi-step `AITemplateGenerator` wizard; builder query prefill; case “Audit this risk” CTAs |
| i18n | en/cy `auditBuilder.*` keys |

## Impact Map
- Audit Template Builder AI Assist modal (wizard replaces one-shot prompt)
- Global search modules (Near Misses + entity_id)
- Incident / Near Miss / RTA / Complaint detail headers
- Governance Library horizon provider when `library_horizon_provider=perplexity`

## Compatibility
- Existing `/generate-template` and `/from-document` unchanged
- Research/Assist Map degrade to empty when keys/services unavailable (fail-closed)
- No schema migrations

## Acceptance Criteria
- AC-01: Intent wizard gathers brief from selected scopes / cases / uploads
- AC-02: Clarifying Q&A updates brief before generate
- AC-03: Similar-template gate can use existing / clone reference / build new (reason logged)
- AC-04: Near misses appear in global search with numeric `entity_id`
- AC-05: `/ai-templates/research` fail-closed when Perplexity key missing
- AC-06: Generate-from-brief returns sections + optional Assist Map suggestions
- AC-07: Incident / Near Miss / RTA / Complaint open builder prefilled (`ai=1&caseType&caseId`)
- AC-08: en/cy strings for wizard + Audit this risk
- AC-09: Unit/FE tests for orchestrator + wizard gather step

## Testing Evidence
- `tests/unit/test_audit_builder_orchestrator.py` (7 passed locally)
- `frontend/src/components/__tests__/AITemplateGenerator.wizard.test.tsx` (vitest passed)
- CI full suite on this PR

## Critical Journeys
- CUJ-01: Audit Builder → intent → gather brief → Q&A → similar gate → generate → add sections
- CUJ-02: Incident detail → Audit this risk → builder opens with case prefilled
- CUJ-03: Research offline / no Perplexity key → honest offline message → generate still works

## Observability
- Horizon/research failures logged at info with exception type only (no payload leak)
- Existing AI 503 path retained for generation unavailable

## Release Plan
1. Squash-merge to main
2. Staging deploy + tip check
3. Smoke CUJ-01 and CUJ-02 on staging
4. Production deploy + tip==LIVE
5. Smoke Audit this risk + wizard gather without research key

## Rollback Plan
- Owner: Platform / Quality
- Rollback steps: revert the merge commit on main and redeploy previous tip; no DB downgrade required

## Evidence Pack
- PR diff + unit/FE tests + Change Ledger + post-deploy tip==LIVE checks

## Gate Checklist
- Gate 0: Scope locked (waves 1–3 orchestration + UX; no migrations)
- Gate 1: API + FE + search wired
- Gate 2: Unit/FE green locally
- Gate 3: CI green
- Gate 4: tip==LIVE staging then prod
- Gate 5: Smoke AC-01–07 / CUJ-01–03
