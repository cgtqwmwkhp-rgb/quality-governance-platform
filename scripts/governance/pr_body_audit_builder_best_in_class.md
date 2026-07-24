# Change Ledger (CL-AUDIT-BUILDER-BEST-IN-CLASS)

## Summary
Best-in-class AI Audit Builder generation: Perplexity research (already on brief) → Gemini schema-enforced template JSON → Claude quality-pass (fail-soft), plus generate timeout fix so the wizard no longer false-fails at 45s.

## Change Ledger
| ID | Change |
|---|---|
| AB-BIC-01 | Gemini `prompt_to_template` uses `response_mime_type` + `response_schema` |
| AB-BIC-02 | New `AuditBuilderGenerationPipeline` (Gemini generate + Claude quality) |
| AB-BIC-03 | `generate-from-brief` returns `models_used` / quality honesty |
| AB-BIC-04 | FE shows pipeline models; generate timeout 300s |
| AB-BIC-05 | Anthropic `complete()` supports longer timeout + temperature |

## Impact Map
- Frontend: AITemplateGenerator generate/preview honesty + timeout
- Backend: gemini_ai_service, audit_builder_generation_pipeline, ai_templates generate-from-brief, ai_models AnthropicClient
- APIs: generate-from-brief response additive fields
- Database: none
- Config/env: uses existing GOOGLE_GEMINI_API_KEY, ANTHROPIC_API_KEY, PERPLEXITY_API_KEY

## Compatibility
- Additive response fields; existing section shape preserved
- Claude quality pass fail-soft when key/errors — Gemini sections still returned
- Breaking changes: None
- Migration plan: N/A
- Rollback strategy (DB): No DB change

## Acceptance Criteria
- AC-01: Generate uses Gemini structured JSON schema path
- AC-02: Claude quality pass runs when Anthropic key present; skipped honestly otherwise
- AC-03: Response includes models_used + quality_pass_available
- AC-04: FE preview shows pipeline line; generate timeout is 300s
- AC-05: Unit tests for normalize + pipeline mocks

## Testing Evidence
- `pytest tests/unit/test_audit_builder_generation_pipeline.py`
- `npm run i18n:check`
- CI on this PR

## Critical Journeys
- CUJ-01: Audit Builder → Generate → preview sections with models_used line
- CUJ-02: Generate without Claude key → still succeeds with quality skipped

## Observability
- quality_pass_notes / models_used on builder_meta
- Existing AI 503 path retained when Gemini unavailable

## Release Plan
1. Squash-merge to main (supersedes open timeout-only PR #1266)
2. SWA prod bake / tip==LIVE
3. Smoke Generate with research + quality line visible

## Rollback Plan
- Rollback trigger: generate regressions / excessive latency
- Rollback steps: revert merge commit and redeploy previous tip
- Owner: Platform / Quality

## Evidence Pack
- PR diff + unit tests + Change Ledger + post-deploy tip==LIVE

## Gate Checklist
- Gate 0: Scope locked (generation pipeline + timeout)
- Gate 1: API additive; FE wired
- Gate 2: CI green
- Gate 3: Staging/SWA verification
- Gate 4: tip==LIVE prod
- Gate 5: Smoke CUJ-01/02
