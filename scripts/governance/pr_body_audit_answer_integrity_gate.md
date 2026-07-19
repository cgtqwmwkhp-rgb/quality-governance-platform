# Change Ledger (CL-AUDIT-ANSWER-INTEGRITY-GATE)

## File allowlist (exclusive)
- `src/domain/services/audit_scoring_service.py`
- `src/domain/services/audit_service.py`
- `src/api/routes/audits.py`
- `tests/unit/test_audit_scoring.py`
- `tests/unit/test_audit_answer_integrity_gate.py`
- `tests/integration/test_inspection_cuj_downstream.py`
- `tests/integration/test_audit_answer_type_matrix.py`
- `docs/audit/ANSWER_INTEGRITY_FREEZE_GAP.md`
- `scripts/governance/pr_body_audit_answer_integrity_gate.md`

**Zero overlap** with FE AuditExecution (PR-B), campaign lanes, UVDB/ISO shells.

## 1) Summary
- **Feature / Change name:** Audit answer integrity PR-A — required completion gate + publish snapshot
- **User goal:** Completing an audit run fails closed when required questions (or evidence) are missing; publish stores a template version snapshot for audit trail.
- **In scope:** `response_is_answered` / `evidence_requirements_met`; `complete_run` gate with `missing_question_ids`; publish type guardrails + `snapshot_json`; unit/integration tests; freeze-gap doc
- **Out of scope:** FE completion UX (PR-B); full freeze-eval against snapshot (parked); path11 rebase
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map
- **Backend:** audit_scoring_service, audit_service, audits complete route
- **APIs:** `POST .../runs/{id}/complete` may 400 with `details.missing_question_ids`
- **Database:** writes `template_versions.snapshot_json` on publish (existing table)

## 3) Compatibility & Data Safety
- #1158 `derive_response_score` / `apply_derived_scores` unchanged
- Evidence checks use `response_json.evidence_asset_ids` (tip spine)
- **Compatibility strategy:** fail-closed completion
- **Breaking changes:** runs that previously completed with missing required answers now 400 (intentional)
- Rollback: revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Required unanswered → complete 400 + missing_question_ids
- [x] AC-02: Evidence-required photo/signature gated via evidence_asset_ids
- [x] AC-03: publish rejects unsupported types; writes snapshot_json

## 5) Testing Evidence
- [x] 31 unit tests passed locally
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incomplete required questions cannot complete a run
- [x] CUJ-02: Publish stores template_versions.snapshot_json

## 7) Observability & Ops
- Error details: `details.missing_question_ids` on 400 complete
- Doc: `docs/audit/ANSWER_INTEGRITY_FREEZE_GAP.md`

## 8) Release Plan
1. Squash-merge when CI green
2. Tip smoke: complete run with missing required → 400; full answers → complete OK

## 9) Rollback Plan
1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Follow-on
- PR-B: AuditExecution persist is_na / evidence_asset_ids; FE jump-to-missing
