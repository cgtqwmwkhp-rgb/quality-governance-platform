# Change Ledger (CL-STANDARDS-WAVE3-PR-E2)

> **Start gate:** SG-D-05 (#1749) LIVE — tip `2b74e82a0cec`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-E2 — Exceptions inbox gate-reason triage.
- **User goal:** After PR-E fail-closed ingest, operators can see *why* a document proposal did not auto-confirm and filter the existing Exceptions inbox by that reason.
- **In scope:** Attach latest `ai_decision_logs` `payload.gate_reason` onto `GET /knowledge-bank/exceptions`; URL-synced `gate_reason` filter; within-page confidence DESC sort; FE badge + why line. No schema change.
- **Out of scope:** E3 re-score on import; E4 CEL writer consolidation; E5 Assist triad; 200–300 queue scale; Alembic; Entra flag; TrapGuard/`covers_framework`; inventing EXACT for CHAS/SSIP/PM/UVDB; cell-aggregate fork; Doc Graph queue changes; bulk-reject API.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-E2-01 | `GET /api/v1/knowledge-bank/exceptions` | No gate outcome on rows | Additive `gate_reason` from latest `evidence_map` log; null if unlogged |
| SG-E2-02 | Inbox query | status / entity / signal / clause / scheme | + `gate_reason=` (known PR-E tokens; unknown → 400) |
| SG-E2-03 | Inbox page order | `created_at` DESC only | Within the existing ≤200 page: confidence DESC, then `created_at` DESC |
| SG-E2-04 | AI Exceptions UI | Confirm/reject queue | Gate-reason badge + filter; URL sync |

## 3) Compatibility & Data Safety
- Additive JSON field. Missing logs stay `null` — never invent a reason.
- Join key matches persist identity `entity_type:entity_id:clause_id`. No CEL column write.
- **Rollback strategy:** Revert merge and redeploy prior tip `2b74e82a0cec`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Auto-confirm gate | PR-E reasons logged only | Unchanged gate; inbox now *shows* the logged reason |
| SoR | CEL + decision log | Unchanged — no second queue |
| TrapGuard / ingest evaluate | Unchanged | Unchanged — this PR does not import `standards_requirement_axis` into TrapGuard/ingest |
| Entra MFA attestation | Flag default false | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `GET /exceptions` rows include `gate_reason` when an `evidence_map` log exists; else null.
- [x] AC-02: Inbox shows the reason on document rows; URL-sync filter `gate_reason`.
- [x] AC-03: Filter returns only matching rows within the existing ≤200 page (honest empty copy).
- [x] AC-04: Within-page sort is confidence DESC, then created_at DESC (null confidence last).
- [x] AC-05: No Alembic; TrapGuard/ingest/`covers_framework`/Entra untouched.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_exceptions_gate_reason.py`
- [x] FE: `frontend/src/pages/__tests__/exceptionsInboxFilters.test.ts`
- [x] FE: `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx`
- [x] FE: `frontend/src/pages/__tests__/knowledgeExceptionsHonesty.test.ts`
- [x] FE: `frontend/src/api/knowledgeBankClient.test.ts`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens AI Exceptions after ingest → document row shows “Below 98% confidence” when that was the logged gate reason.
- [x] CUJ-02: Operator filters `gate_reason=below_threshold` → URL shares; unmatched page is honest “not a global zero”.

## 7) Observability & Ops
- Unknown `gate_reason` query → 400 (`Invalid gate_reason`).
- Inbox page cap remains 200 (queue scale is a later slice).

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `2b74e82a0cec` (`STACK_MAX=1`).
2. Focused unit/Vitest green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Invented gate reasons; TrapGuard/ingest change; Entra flag flipped; CEL schema write.
- **Rollback steps:** Revert merge; redeploy prior tip `2b74e82a0cec` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_e2.md`
- Parent LIVE gate: **PR #1749** (SG-D-05) @ `2b74e82a0cec`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1749 LIVE confirmed
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
