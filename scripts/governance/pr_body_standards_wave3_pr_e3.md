# Change Ledger (CL-STANDARDS-WAVE3-PR-E3)

> **Start gate:** PR-E2 (#1750) LIVE — tip `1d39aa0367c3`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-E3 — re-score existing document evidence when the 5064 matrix edition changes.
- **User goal:** After a 5064 import (new edition or reactivation), machine-confirmed document→clause links that no longer pass the PR-E ingest gate are demoted to `proposed` so they land in Exceptions. A human confirms. Stale EXACT auto-confirms cannot survive a tighter matrix.
- **In scope:** Hook after alignment apply when `created` or `reactivated`; re-run `evaluate()`; demote violations; log `evidence_map` `gate_reason` so the E2 inbox shows why; seed path shares the same hook. No Alembic.
- **Out of scope:** E4 CEL writer consolidation; E5 Assist triad; 200–300 inbox queue scale; auto-promoting proposed rows; TrapGuard `covers_framework`; inventing EXACT for CHAS/SSIP/PM/UVDB; cell-aggregate fork; Entra flag; Doc Graph.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-E3-01 | `POST /alignment/import/apply` | Matrix edition activates; existing CEL unchanged | After a real edition change, machine-confirmed document CEL is re-scored; additive `rescore` counts on the response |
| SG-E3-02 | Seed `seed_5064_alignment` | Apply only | Same rescore hook as the API (dry-run still writes nothing) |
| SG-E3-03 | Machine-confirmed CEL | Survived a NEAR/DIFFERENT/cover-block re-import | Demoted to `proposed`; `auto_applied=false`; Exceptions inbox |
| SG-E3-04 | Human confirmer / MANUAL | Could be mixed with machine rows | Preserved — never demoted by this pass |
| SG-E3-05 | Proposed CEL | Unchanged | Still unchanged — this pass never auto-promotes |

## 3) Compatibility & Data Safety
- Additive apply-response field `rescore` (`null` when the checksum was already live).
- Demotion is fail-closed (CONFIRMED → PROPOSED). No schema change.
- Same-checksum re-apply does not rescore.
- Scan cap 5000 with `truncated: true` when hit — honest, not silent skip-without-flag.
- **Rollback strategy:** Revert merge and redeploy prior tip `1d39aa0367c3`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Stale machine coverage | Auto-confirmed CEL survived a tighter 5064 edition | Re-scored through PR-E `evaluate()`; violations → Exceptions |
| Human confirmer (D15) | Untouched by import | Still untouched — `confirmed_by_id` / MANUAL preserved |
| SoR | 5064 payload + CEL | Unchanged — no second obligation register; no cell-aggregate fork |
| TrapGuard / `covers_framework` | Alignment-edge-only | Untouched — this PR does not import `standards_requirement_axis` into TrapGuard/ingest |
| Entra MFA attestation | Flag default false | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: NEAR / DIFFERENT / cover-block / not-EXACT-for-framework demote machine-confirmed document CEL to `proposed`.
- [x] AC-02: Still-valid ISO EXACT ≥98% machine-confirmed rows stay confirmed (no spurious demote).
- [x] AC-03: Human `confirmed_by_id` and MANUAL links are not demoted.
- [x] AC-04: Proposed EXACT rows are not auto-promoted. Same-checksum apply does not rescore.
- [x] AC-05: No Alembic; TrapGuard/`covers_framework`/Entra/`standards_requirement_axis` in ingest untouched.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_matrix_rescore.py`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator re-imports 5064 with a NEAR (or DIFFERENT) row that previously auto-confirmed → that document link is now `proposed` and Exceptions can show the logged `gate_reason`.
- [x] CUJ-02: Operator had personally confirmed a link → re-import leaves the confirmer stamp and `confirmed` status.

## 7) Observability & Ops
- Demotions write `ai_decision_logs` `action=evidence_map` with `payload.rescore=true` and `gate_reason` so PR-E2 inbox triage keeps working.
- Apply JSON gains `rescore: {scanned, demoted, kept_confirmed, preserved_human, skipped, truncated}` or `null`.
- Truncation at 5000 is logged at WARNING.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `1d39aa0367c3` (`STACK_MAX=1`).
2. Focused unit tests green; open PR with this ledger.
3. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Human confirmer stamps demoted; mass false demotion of still-valid EXACT; TrapGuard/`covers_framework`/Entra changed; invented EXACT for CHAS/SSIP/PM/UVDB; cell-aggregate fork.
- **Rollback steps:** Revert merge; redeploy prior tip `1d39aa0367c3` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_e3.md`
- Parent LIVE gate: **PR #1750** (PR-E2) @ `1d39aa0367c3`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1750 LIVE confirmed
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
