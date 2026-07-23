# Change Ledger (CL-AI-AUDIT-BUILDER-WAVES)

## Summary
Ship the risk-driven AI Audit Builder conveyor: intent wizard + platform context orchestrator, near-miss search, live Perplexity research, similar-template gate, generate-from-brief with Assist Map suggestions, and case→builder entry points.

## Scope
- **In scope:** Audit Builder orchestrator; `/ai-templates` gather-brief / apply-qa / similar-templates / research / generate-from-brief; Perplexity live provider (fail-closed); near misses in SearchService + `entity_id`; FE multi-step wizard; case detail “Audit this risk” entry points; en/cy i18n; unit tests; this Change Ledger
- **Out of scope:** Embedding-based similar-template scoring; new DB migrations; replacing Gemini generation provider

## Acceptance criteria
- [x] AC-01: Intent wizard gathers brief from selected scopes / cases / uploads
- [x] AC-02: Clarifying Q&A updates brief before generate
- [x] AC-03: Similar-template gate can use existing / clone reference / build new (reason logged)
- [x] AC-04: Near misses appear in global search with numeric `entity_id`
- [x] AC-05: `/ai-templates/research` fail-closed when Perplexity key missing
- [x] AC-06: Generate-from-brief returns sections + optional Assist Map suggestions
- [x] AC-07: Incident / Near Miss / RTA / Complaint can open builder prefilled (`ai=1&caseType&caseId`)
- [x] AC-08: en/cy strings for wizard + Audit this risk
- [x] AC-09: Unit tests for orchestrator prompt/QA + Perplexity fail-closed parse path

## Test plan
- [ ] Unit: `pytest tests/unit/test_audit_builder_orchestrator.py`
- [ ] CI green on PR
- [ ] Staging smoke: open Audit Builder wizard → gather brief without research key → generate still works
- [ ] Staging: Incident detail → Audit this risk opens `/audit-templates/new?ai=1...`
- [ ] Prod version tip after merge/deploy

## Gates
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [ ] **Gate 1:** CI / review
- [ ] **Gate 2:** Staging verify
- [ ] **Gate 3:** Production live
