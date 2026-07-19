# Change Ledger (CL-AUDIT-ANSWER-INTEGRITY-FE)

## File allowlist (exclusive)
- `frontend/src/pages/auditAnswerIntegrity.ts`
- `frontend/src/pages/__tests__/auditAnswerIntegrity.test.ts`
- `frontend/src/pages/AuditExecution.tsx`
- `frontend/src/api/auditsClient.ts`
- `frontend/src/pages/audit-builder/templateHelpers.ts`
- `frontend/src/pages/audit-builder/templateHelpers.test.ts`
- `frontend/src/pages/AuditTemplateBuilder.tsx`
- `scripts/governance/pr_body_audit_answer_integrity_fe.md`

**Zero overlap** with PR-A backend (#1165). Does not rebase path11.

## 1) Summary
- **Feature / Change name:** Audit answer integrity PR-B — FE completion UX + publish guards
- **User goal:** Auditors see which required questions block complete; save persists `is_na` + `response_json` (evidence_asset_ids + selected); builder blocks unpublishable types.
- **In scope:** AuditExecution save/complete UX; templateHelpers publishable types; vitest; Change Ledger
- **Out of scope:** Backend gate (PR-A #1165); MobileAuditExecution parity; freeze-eval
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map
- **Frontend:** AuditExecution, AuditTemplateBuilder, templateHelpers, auditsClient DTOs
- **Backend:** None

## 3) Compatibility & Data Safety
- Preserves #1158 evidence-assets spine (`evidence_asset_ids`)
- **Compatibility strategy:** FE tolerant if PR-A not yet merged (generic error path)
- **Breaking changes:** None
- Rollback: revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Save payloads include `is_na` and merged `response_json`
- [x] AC-02: Complete 400 with `missing_question_ids` → toast + jump/highlight
- [x] AC-03: Publish pre-check rejects unsupported question types

## 5) Testing Evidence
- [x] Vitest auditAnswerIntegrity + templateHelpers
- [x] ESLint clean
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incomplete required answers — complete surfaces missing questions
- [x] CUJ-02: Photo/signature evidence_asset_ids round-trip on save

## 7) Observability & Ops
- User-visible toast/banner on complete gate failure; no new metrics

## 8) Release Plan
1. Prefer merge after PR-A #1165 (gate API) for full E2E
2. Squash-merge when CI green; tip smoke AuditExecution complete path

## 9) Rollback Plan
1. Revert squash commit on `main`
2. Redeploy previous SHA
- **Rollback steps:** revert PR squash merge
- **Owner:** Platform / Assurance engineering

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Depends on: PR-A #1165 for server `missing_question_ids`

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready
