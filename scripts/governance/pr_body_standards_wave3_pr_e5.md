# Change Ledger (CL-STANDARDS-WAVE3-PR-E5)

> **Start gate:** PR-E4 (#1753) LIVE — tip `6a9bbc4c1483`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-E5 — route Audit Builder Map CEL mirrors through the sole writer.
- **User goal:** Assist Map accept/edit/reject still mirrors to `compliance_evidence_links`, but no longer constructs rows beside the sole writer. D15 human confirmer stamps are preserved; AI accept never invents a human confirmer.
- **In scope:** `BuilderStandardLinkService._mirror_evidence_link` calls `apply_ingest_mapping`; drop builder from `REMAINING_CEL_WRITERS`. No Alembic. No Assist Finder/Guardian/Coach UI.
- **Out of scope:** Finder/Guardian/Coach triad product; `external_audit_promotion_service` / `audit_service` constructors; Exceptions 200–300 queue scale; TrapGuard `covers_framework`; inventing EXACT for CHAS/SSIP/PM/UVDB; cell-aggregate fork; Entra flag.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-E5-01 | Builder `_mirror_evidence_link` | Constructed CEL inline | Calls `apply_ingest_mapping` (`commit=False`) |
| SG-E5-02 | D15 on Map reject | Could overwrite a human-confirmed row | Human MANUAL / `confirmed_by_id` stamps preserved; JSON reject still recorded on the question |
| SG-E5-03 | Remaining-writer list | Builder listed as blocked on signature | Builder removed; promotion + audit_service remain |

## 3) Compatibility & Data Safety
- Accept/edit still land as `linked_by=AI`, `status=confirmed`, `auto_applied=False`, `confirmed_by_id` null.
- Reject of a non-human row still sets `rejected` and appends `Rejected:` notes.
- Question `map_standard_links` JSON persist is unchanged.
- Writer still does not call `evaluate()`. Version pin still skipped for `audit_question`.
- **Rollback strategy:** Revert merge and redeploy prior tip `6a9bbc4c1483`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CEL write paths | Builder constructed rows beside the sole writer | Map mirror uses the sole writer |
| Human confirmer (D15) | Builder could rewrite status on a human row | Same preserve rule as ingest |
| PR-E auto-confirm gate | Unchanged | Unchanged — writer does not call `evaluate()` |
| TrapGuard / Entra | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Assist Map accept still mirrors to CEL through the sole writer; no `ComplianceEvidenceLink(` in `builder_standard_link_service.py`.
- [x] AC-02: New AI accept is `linked_by=AI`, `confirmed_by_id` null. Existing MANUAL / `confirmed_by_id` rows keep the stamp on reject.
- [x] AC-03: `remaining_writer_report()` drops builder; promotion and audit_service remain.
- [x] AC-04: No Alembic; TrapGuard/`covers_framework`/Entra/`standards_requirement_axis` in ingest untouched; no Finder/Guardian/Coach UI.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_builder_standard_link_service.py`
- [x] Unit: `tests/unit/test_standards_cel_ingest_writer.py`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator accepts an Assist Map suggestion → CEL confirmed, no human stamp.
- [x] CUJ-02: Operator rejects a suggestion on a clause a human already confirmed → confirmer stamp and confirmed status remain.

## 7) Observability & Ops
- `ai_decision_logs` `builder_standard_link_*` payload still carries `evidence_link_id`.
- Remaining CEL writers are still listed via `remaining_writer_report()`.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `6a9bbc4c1483` (`STACK_MAX=1`).
2. Focused unit tests green; open PR with this ledger.
3. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Human confirmer stamps wiped on Map reject; TrapGuard/`covers_framework`/Entra changed; Assist triad UI invented; remaining writers silently swallowed.
- **Rollback steps:** Revert merge; redeploy prior tip `6a9bbc4c1483` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_e5.md`
- Parent LIVE gate: **PR #1753** (PR-E4) @ `6a9bbc4c1483`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1753 LIVE confirmed
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
