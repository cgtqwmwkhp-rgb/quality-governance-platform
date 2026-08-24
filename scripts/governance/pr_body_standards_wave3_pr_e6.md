# Change Ledger (CL-STANDARDS-WAVE3-PR-E6)

> **Start gate:** PR-E5 (#1754) LIVE — tip `5ab223536b4c`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-E6 — route external-audit promotion CEL writes through the sole writer.
- **User goal:** Promoting an imported audit still mirrors findings and source documents onto `compliance_evidence_links`, including revive of a soft-deleted row, but no longer constructs rows beside the sole writer. The promotion transaction still flushes after the clause loop.
- **In scope:** `apply_promotion_mapping` on `compliance_evidence_link_writer`; both `_link_evidence_for_finding` and `_link_source_document_evidence` call it; drop promotion from `REMAINING_CEL_WRITERS`. No Alembic. No Assist triad UI.
- **Out of scope:** Finder/Guardian/Coach; `audit_service` leftover (E7); Exceptions 200–300 scale; TrapGuard `covers_framework`; inventing EXACT for CHAS/SSIP/PM/UVDB; cell-aggregate fork; Entra flag.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-E6-01 | Finding promotion CEL | Inline `ComplianceEvidenceLink(` | `apply_promotion_mapping` then caller `flush` |
| SG-E6-02 | Source-document promotion CEL | Inline construct + version pin | Same writer; pin still runs for `document` |
| SG-E6-03 | Remaining-writer list | Promotion listed as blocked on flush | Promotion removed; audit_service remains |

## 3) Compatibility & Data Safety
- Soft-deleted rows are still revived (`deleted_at` cleared). `linked_by=AUTO` still overwrites, including a previous MANUAL row — existing import tests require that.
- Writer does not commit; promotion still flushes once after the clause loop (same transaction boundary).
- Document version pin still runs for `entity_type=document` only.
- **Rollback strategy:** Revert merge and redeploy prior tip `5ab223536b4c`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CEL write paths | Promotion constructed rows beside the sole writer | Promotion uses the sole writer |
| Revive on re-promote | Soft-deleted PK reused | Unchanged |
| TrapGuard / Entra | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: No `ComplianceEvidenceLink(` in `external_audit_promotion_service.py`.
- [x] AC-02: Re-promote of a soft-deleted finding CEL clears `deleted_at` and sets `linked_by=AUTO`.
- [x] AC-03: `remaining_writer_report()` drops promotion; audit_service remains.
- [x] AC-04: No Alembic; TrapGuard/`covers_framework`/Entra untouched; writer does not call `evaluate()`.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_external_audit_import_service.py` (revive)
- [x] Unit: `tests/unit/test_external_audit_promotion_service.py`
- [x] Unit: `tests/unit/test_standards_cel_ingest_writer.py`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Re-promote a finding whose CEL was soft-deleted → same row revived, AUTO.
- [x] CUJ-02: Source-document promotion still pins document version via the writer.

## 7) Observability & Ops
- Remaining CEL writers still listed via `remaining_writer_report()` (audit_service only).

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `5ab223536b4c` (`STACK_MAX=1`).
2. Focused unit tests green; open PR with this ledger.
3. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Soft-deleted rows no longer revive; TrapGuard/`covers_framework`/Entra changed; Assist triad invented; audit_service silently swallowed.
- **Rollback steps:** Revert merge; redeploy prior tip `5ab223536b4c` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_e6.md`
- Parent LIVE gate: **PR #1754** (PR-E5) @ `5ab223536b4c`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1754 LIVE confirmed
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
