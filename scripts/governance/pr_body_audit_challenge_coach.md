# Change Ledger (CL-AUDIT-CHALLENGE-COACH)

## Summary
World-leading **Check & Challenge coach** for Audit Builder templates: an async, Azure-safe dual-agent (assessor critic + author rewriter) session with cited standards/OEM grounding, chip prompts + free chat, Accept/Reject/Edit proposal diffs, and Apply-to-template — mounted on the wizard Preview step and as a persistent rail action on the Builder (after AI Apply). Wave A spine + Wave B intelligence delivered in one branch; Wave C (history UI polish, golden eval harness, e2e) tracked as follow-on.

## Change Ledger
| ID | Change |
|---|---|
| ACC-01 | New tables: `audit_challenge_sessions`, `audit_challenge_turns`, `audit_challenge_proposals` (migration `20260816_audit_challenge`, single clean alembic head) |
| ACC-02 | `AuditChallengeSession/Turn/Proposal` models wired into `src/domain/models/__init__.py` |
| ACC-03 | `AuditChallengePipeline`: Ground (Assist Map + Perplexity OEM) → Critic (Claude, heuristic fail-soft) → Author (deterministic proposal diffs, Gemini-ready hook) → citation validation (drops ungrounded ISO/OEM refs) |
| ACC-04 | `AuditChallengeService`: session lifecycle, turns, decide (accept/reject/edit), apply-accepted merge into section snapshot |
| ACC-05 | Celery task `process_audit_challenge_session` (+ inline fallback), registered in `CELERY_TASK_MODULES` |
| ACC-06 | API under `/api/v1/ai-templates/challenge/`: `POST sessions`, `GET sessions/{id}`, `POST sessions/{id}/messages`, `POST sessions/{id}/proposals/{id}/decide`, `POST sessions/{id}/apply` — async create+poll, mirrors Safety Insights pattern (Celery `.delay()` with `BackgroundTasks` inline fallback so a request never blocks past Azure's ~230s gateway limit) |
| ACC-07 | FE client `auditChallengeClient.ts` (+ registered on shared `api/client.ts`), `CheckChallengeCoach.tsx` + `ProposalDiffCard.tsx` components (chips, chat, 2s poll, citations, accept/reject/edit, apply) |
| ACC-08 | Mounted in wizard Preview (`AITemplateGenerator.tsx`) and as a rail action on `AuditTemplateBuilder.tsx`, auto-opened after AI Apply |
| ACC-09 | Fixed pre-existing gap: `mapAISectionsToLocal` now merges `standardSuggestions` into `question.standardLinks` on Apply (previously dropped silently) |
| ACC-10 | Bugfix caught by new tests: `decide_proposal` now maps API verbs (`accept`/`reject`/`edit`) to persisted enum states (`accepted`/`rejected`/`edited`) — was raising `INVALID_DECISION` for every accept/reject call |

## Impact Map
- **Frontend:** `AITemplateGenerator.tsx` (Preview step "Check & Challenge" button), `AuditTemplateBuilder.tsx` (rail button + post-Apply auto-open), new `components/auditChallenge/{CheckChallengeCoach,ProposalDiffCard}.tsx`, `api/auditChallengeClient.ts`, `api/client.ts`, `pages/audit-builder/templateHelpers.ts`
- **Backend:** `api/routes/ai_templates.py` (challenge sub-router), `domain/services/audit_challenge_{service,pipeline}.py`, `domain/models/audit_challenge.py`, `domain/models/__init__.py`, `infrastructure/tasks/audit_challenge_tasks.py`, `infrastructure/tasks/celery_app.py`
- **APIs (new, additive):** `/api/v1/ai-templates/challenge/sessions[/*]`
- **Database:** 3 new tables, 1 migration, single alembic head verified (`alembic heads`)
- **Workflows/jobs:** new Celery task `process_audit_challenge_session` (queue `default`, soft limit 180s)
- **Config/env:** reuses `ANTHROPIC_API_KEY` / `GOOGLE_GEMINI_API_KEY` / Perplexity research; new optional `AUDIT_CHALLENGE_INLINE=1` to force inline processing (parity with `SAFETY_INSIGHTS_INLINE`)

## Compatibility
- Purely additive tables/endpoints/components — no existing schema or contract changes.
- Fail-soft by design: no Claude key → heuristic critic still returns useful, cited (or honestly empty) findings; no Gemini author → deterministic proposal diffs.
- Breaking changes: none.
- Migration plan: standard `alembic upgrade head`; downgrade drops the 3 new tables in dependency order.
- Rollback strategy (DB): run `alembic downgrade 20260815_safety_insights`, or simply leave tables unused if reverting only the app code.

## Acceptance Criteria
- AC-01: Session create/poll/decide/apply endpoints match the plan's contract and permissions (`audit:create`)
- AC-02: Celery enqueue with inline `BackgroundTasks` fallback — request never blocks on the AI pipeline
- AC-03: Heuristic critic always emits ≥1 scoring + ≥1 field_usability finding even with zero AI keys configured
- AC-04: Citation validation drops any ISO/OEM reference not present in grounding (no hallucinated citations reach the UI)
- AC-05: Accept/Reject/Edit persists correctly; Apply merges only accepted/edited proposals into the section snapshot
- AC-06: Coach reachable from both the wizard Preview step and the Builder rail (auto-opens after AI Apply)
- AC-07: `standardSuggestions` from AI generation now land on `question.standardLinks` (previously silently dropped)

## Testing Evidence
- `pytest tests/unit/test_audit_challenge_pipeline.py tests/unit/test_audit_challenge_service.py` — 27 passed
- `pytest tests/unit` — 3231 passed, 7 skipped (no regressions)
- `pytest tests/unit/test_celery_app_config.py tests/unit/infrastructure/test_celery_task_registration.py` — 7 passed
- `npx tsc --noEmit` — clean
- `npx eslint` on all touched frontend files — 0 errors
- `npx vitest run` — templateHelpers, auditChallengeClient, AITemplateGenerator wizard, client.ts — all green
- `alembic heads` — single head (`20260816_audit_challenge`), full `src.main:app` boots and registers all 5 challenge routes

## Critical Journeys
- CUJ-01: Generate a template in the wizard → open Check & Challenge on Preview → run a chip → accept a proposal → Apply merges the fix into the previewed sections
- CUJ-02: On the Builder (existing or new template) → Check & Challenge rail → free-text challenge → Accept/Edit/Reject loop → Apply patches live section state
- CUJ-03: No AI keys configured → coach still returns a heuristic critique with real findings (never a blank/broken run)

## Observability
- `session.models_used_json` records which of critic/author/research actually ran (honesty line, same pattern as Audit Builder generation)
- `session.error_code` / `error_detail` populated on Celery/inline failure; session status flips to `failed` rather than hanging
- No new logs/metrics/alerts beyond existing structured logging conventions

## Release Plan
1. CI green on this PR (unit + lint + typecheck)
2. Squash-merge to `main` after review
3. SWA prod bake, smoke: open a template, run Check & Challenge, accept a proposal, Apply

## Rollback Plan
- Rollback trigger: challenge session errors blocking Builder usage, or Celery queue saturation
- Rollback steps: revert merge commit; DB tables are additive and inert if the app code is reverted (no forced downgrade needed unless reclaiming the migration slot)
- Owner: Platform / Quality

## Evidence Pack
- PR diff + unit test run output + this Change Ledger

## Gate Checklist
- Gate 0: Scope locked (Wave A spine + Wave B intelligence; Wave C follow-on)
- Gate 1: API additive, FE wired at both mount points
- Gate 2: CI green (this PR)
- Gate 3: Staging/SWA verification (post-merge)
- Gate 4: tip==LIVE prod (post-merge)
- Gate 5: Smoke CUJ-01/02/03
