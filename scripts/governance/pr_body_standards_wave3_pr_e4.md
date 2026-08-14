# Change Ledger (CL-STANDARDS-WAVE3-PR-E4)

> **Start gate:** PR-E3 (#1752) LIVE — tip `6f8ca1c1cf9c`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-E4 — route governed-knowledge ingest through the sole CEL writer.
- **User goal:** Library ingest no longer constructs `compliance_evidence_links` rows beside the sole writer. One write path applies D15 confirmer hygiene and version pinning; the PR-E gate still decides status.
- **In scope:** `apply_ingest_mapping` on `compliance_evidence_link_writer`; `GovernedKnowledgeService._persist_mapping` calls it; drop GKS from `REMAINING_CEL_WRITERS`. No Alembic.
- **Out of scope:** audit_service / builder_standard_link / external_audit_promotion writers; E5 Assist triad; TrapGuard `covers_framework`; inventing EXACT for CHAS/SSIP/PM/UVDB; cell-aggregate fork; Entra flag.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-E4-01 | GKS `_persist_mapping` | Constructed CEL inline | Calls `apply_ingest_mapping` |
| SG-E4-02 | Sole writer | HTTP link + EXACT-share create-if-absent | + ingest mapping (gate status, human preserve) |
| SG-E4-03 | Remaining-writer list | GKS listed as blocked on PR-E | GKS removed; audit/builder/promotion remain |

## 3) Compatibility & Data Safety
- Behaviour-preserving for the PR-E gate and human confirmer preserve. New rows are never treated as human-confirmed.
- Version pin still runs for `entity_type=document`.
- Decision logs still written by GKS (`evidence_map` + `gate_reason`).
- **Rollback strategy:** Revert merge and redeploy prior tip `6f8ca1c1cf9c`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CEL write paths | GKS wrote rows beside the sole writer | Ingest uses the sole writer |
| Human confirmer (D15) | Preserved in GKS inline | Same rule, now in the writer |
| PR-E auto-confirm gate | Unchanged `evaluate()` | Unchanged — writer does not call `evaluate()` |
| TrapGuard / Entra | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: New auto-confirm ingest write is `linked_by=AI`, `confirmed_by_id` null.
- [x] AC-02: Existing MANUAL / `confirmed_by_id` rows keep the stamp; status not demoted by ingest.
- [x] AC-03: GKS is absent from `remaining_writer_report()`; audit/builder/promotion remain.
- [x] AC-04: No Alembic; TrapGuard/`covers_framework`/Entra/`standards_requirement_axis` in ingest untouched.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_cel_ingest_writer.py`
- [x] Unit: `tests/unit/test_lib_wi1_cel_harden_scheme.py` (existing persist mapping)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Map a high-confidence document that the gate auto-confirms → CEL confirmed, no human stamp.
- [x] CUJ-02: Remap a document the operator already confirmed → confirmer stamp and confirmed status remain.

## 7) Observability & Ops
- `ai_decision_logs` `evidence_map` payload still carries `gate_reason` / `human_confirmed_preserved`.
- Remaining CEL writers are still listed via `remaining_writer_report()`.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `6f8ca1c1cf9c` (`STACK_MAX=1`).
2. Focused unit tests green; open PR with this ledger.
3. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Human confirmer stamps wiped on remap; auto-confirm without gate; TrapGuard/`covers_framework`/Entra changed; remaining writers silently swallowed.
- **Rollback steps:** Revert merge; redeploy prior tip `6f8ca1c1cf9c` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_e4.md`
- Parent LIVE gate: **PR #1752** (PR-E3) @ `6f8ca1c1cf9c`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1752 LIVE confirmed
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
