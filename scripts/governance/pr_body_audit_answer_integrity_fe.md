# Change Ledger (CL-AUDIT-ANSWER-INTEGRITY-FE)

## File allowlist (exclusive)
- `frontend/src/pages/AuditExecution.tsx`
- `frontend/src/pages/auditAnswerIntegrity.ts`
- `frontend/src/pages/auditExecutionPhotoEvidence.ts` (read-only spine — no behavioural change)
- `frontend/src/pages/audit-builder/templateHelpers.ts`
- `frontend/src/pages/AuditTemplateBuilder.tsx`
- `frontend/src/api/auditsClient.ts` (DTO `is_na` only)
- `frontend/src/pages/__tests__/auditAnswerIntegrity.test.ts`
- `frontend/src/pages/audit-builder/templateHelpers.test.ts`
- `scripts/governance/pr_body_audit_answer_integrity_fe.md`

**Zero overlap** with PR-A backend (`feat/audit-answer-integrity-gate`), campaign lanes, or path11 wholesale rebase.

## 1) Summary
- **Feature / Change name:** Audit answer integrity PR-B — frontend persistence + completion UX
- **User goal:** Execution UI sends `is_na` and merged `response_json` (evidence spine + selected options) so PR-A complete gate passes when answers are truly complete; incomplete completes surface `missing_question_ids` with jump-to-question UX.
- **In scope:** Save/complete payloads; 400 parsing + toast + highlight first missing question; publish-time type pre-check in builder; vitest helpers
- **Out of scope:** Backend Python; OpenAPI regen; MobileAuditExecution parity (follow-on)
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map
- **Frontend:** AuditExecution save/complete; templateHelpers publish guards; AuditTemplateBuilder validation
- **APIs consumed:** Tolerates PR-A `POST .../complete` 400 with `error.details.missing_question_ids` (graceful no-op until PR-A merges)
- **Database:** None

## 3) Compatibility & Data Safety
- Preserves #1158 evidence-assets spine (`evidence_asset_ids` in `response_json`)
- Adds `selected` for checklist/radio and `is_na` for yes/no N/A without removing photo/signature upload flow
- Tolerant reader on load: hydrates `is_na`, `selected`, and existing `evidence_asset_ids`
- Rollback: revert commit

## 4) Acceptance Criteria
- [x] Save/create/update payloads include `is_na` when response is N/A
- [x] `response_json` merges `evidence_asset_ids` + checklist/radio `selected`
- [x] Complete 400 → toast + error banner + navigate/highlight first `missing_question_ids` entry
- [x] Builder publish pre-check uses `EXECUTABLE_QUESTION_TYPES` / rejects `file`
- [x] Vitest for helpers + error parsing

## 5) Testing Evidence
- [x] `npm run test -- auditAnswerIntegrity templateHelpers` (local)
- [ ] CI green — parent PR

## 6) Follow-on
- MobileAuditExecution parity
- E2E complete-gate smoke after PR-A merges to main
