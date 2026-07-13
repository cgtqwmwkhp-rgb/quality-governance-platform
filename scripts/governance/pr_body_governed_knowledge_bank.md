# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** AI-first Governed Knowledge Bank
- **User goal (1–2 lines):** Upload and manage documents so AI auto-maps evidence to ISO/UVDB/Planet Mark, watches UK regulatory change, distributes with quizzes/Q&A, and only surfaces exceptions for humans.
- **In scope:** Multi-scheme evidence mapping with confidence-gated auto-apply; document detail + document control UI; My Reading + Q&A; AI questionnaires; UK curated regulatory watch + Celery beat; version rematch/quiz stale.
- **Out of scope:** Replacing SharePoint as file store; unrestricted open-web crawl; fully autonomous certify without exception path for safety-critical types.
- **Feature flag / kill switch:** None (additive `/knowledge-bank` APIs; existing library continues if AI keys absent — Partial honesty via existing Documents CUJ patterns)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `/documents/:id`, `/document-control`, `/my-reading`, `/knowledge-exceptions`; Standards scan button; Compliance Automation Watch tab; Layout nav links
- **Backend (handlers/services):** `GovernedKnowledgeService`, `RegulatoryWatchService`, document upload mapping hook, controlled-version rematch hook
- **APIs (endpoints changed/added):** `/api/v1/knowledge-bank/*` (map, evidence, exceptions, scan, quiz, discussions, regulatory-watch)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** New Pydantic response models on knowledge-bank router; frontend `knowledgeBankApi` / `documentControlApi`
- **Database (migrations/entities/indexes):** `20260713_governed_kb` — CEL status/scheme/auto_applied/rationale + discussion/quiz/impact/ai_decision_log tables
- **Workflows/jobs/queues (if any):** Celery `run_regulatory_watch` weekly Monday 05:30 UTC
- **Config/env/flags:** Uses existing Anthropic / Voyage / Pinecone keys
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — legacy CEL rows without status treat manual links as confirmed via `effective_status`
- **Breaking changes:** None
- **Migration plan:** Alembic upgrade `20260713_governed_kb` on staging then prod deploy
- **Rollback strategy (DB):** Columns nullable / server defaults; tables unused if rolled back app; drop migration down() available

## 4) Acceptance Criteria (AC)
- [ ] AC-01: Upload triggers multi-scheme mapping; links ≥0.85 auto-confirm except RAMS/COSHH/MSDS/SDS which stay proposed
- [ ] AC-02: Document detail Standards/Evidence tab lists links; exceptions inbox supports confirm/reject/bulk
- [ ] AC-03: New standard Scan KB returns candidates; new controlled version rematches evidence and marks quizzes stale / drafts new quiz
- [ ] AC-04: My Reading + Q&A + AI quiz generate/approve paths work with honesty toasts on failure
- [ ] AC-05: Regulatory watch poll creates updates/impacts from curated UK feeds (or safe fallback)

## 5) Testing Evidence (link to runs)
- [x] Lint (CI)
- [x] Typecheck (`tsc --noEmit` local)
- [x] Build (CI)
- [x] Unit tests (`test_governed_knowledge_service` 22 + `test_regulatory_watch_service` 4)
- [ ] Integration tests
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [ ] CUJ-01: Operator opens Library document → Map evidence → confirm exception → see Standards tab updated
- [ ] CUJ-02: Operator runs Standards Scan KB / Watch poll → impacts or candidates appear without silent failure

## 7) Observability & Ops
- **Logs:** `AiDecisionLog` for map/rematch/quiz/watch; upload mapping failures logged without failing upload
- **Metrics:** Existing `/readyz` email/AI status; watch returns counts
- **Alerts:** Prefer existing upstream breakers (`document_ai`)
- **Runbook updates:** Human unlock SMTP remains separate; watch uses curated allowlist only

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Migrate; hit `/api/v1/knowledge-bank/exceptions`; open `/documents/:id`
- **Canary plan:** Full promote after staging green (no canary % in this pipeline)
- **Prod post-deploy checks:** `/api/v1/meta/version` SHA match; `/readyz`; smoke Map Evidence on one non-prod doc in staging first

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Knowledge-bank routes 5xx rate spike; migration failure; bad auto-links flooding confirmed evidence
- **Rollback steps:** Revert deploy to previous App Service slot/SHA; leave DB additive columns; optionally set upload hook no-op via hotfix if needed
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): PR #921 checks
- Staging deploy evidence: pending after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
