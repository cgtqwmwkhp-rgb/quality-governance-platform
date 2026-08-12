# Change Ledger (CL-STANDARDS-WAVE3-PR-E)

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-E slice 1 — ingest auto-confirm gate.
- **User goal:** Stop AI document mapping from machine-confirming evidence at 0.85 with no EXACT / open-NC checks; require ≥98% + EXACT + cover-clear; preserve human confirmer stamps on remap.
- **In scope:** `standards_ingest_gate`, resolve_link_status fail-closed, CoverBlockIndex, human-preserve in `_persist_mapping`, map-evidence gate summary, index job per-tenant context cache.
- **Out of scope:** Exceptions inbox triage (E2), re-score on import (E3), CEL writer consolidation (E4), Finder/Guardian/Coach Assist (E5), 200–300 doc queue scale.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-E-01 | resolve_link_status | Auto-confirm ≥0.85 | Gate required; else PROPOSED |
| SG-E-02 | Ingest mapping | No alignment / NC check | ≥0.98 + EXACT + not cover-blocked |
| SG-E-03 | Remap existing CEL | Could wipe human confirmer | Preserves MANUAL / confirmed_by_id |
| SG-E-04 | map-evidence API | links only | + `auto_confirm_gate` tallies |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive response field; fail-closed writes (more PROPOSED, never invent CONFIRMED).
- **Tolerant reader / strict writer applied?** Yes.
- **Breaking changes:** Callers of `map_document_to_schemes` now receive `MapDocumentResult` (`.links`).
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Machine-confirmed coverage | 85% confidence, no EXACT/NC gate | ≥98% + EXACT + cover-clear |
| Human confirmer (D15) | Remap could null stamps | Preserved on human/manual rows |
| Unloaded matrix | Could still auto-confirm | `matrix_not_loaded` → PROPOSED |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Threshold 0.979 refuse / 0.98 allow on EXACT clean cell.
- [x] AC-02: No matrix / DIFFERENT / NEAR / open NC refuse at 1.0 confidence.
- [x] AC-03: `resolve_link_status` without gate always PROPOSED; `AUTO_CONFIRM_THRESHOLD` stays 0.85 for regulatory watch.
- [x] AC-04: Human-confirmed rows not demoted by remap status rewrite.
- [ ] AC-05: Hosted CI green; STG=PROD tip LIVE after merge.

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_standards_ingest_gate` + updated `test_governed_knowledge_service` (42 passed)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Map procedure at 90% with no matrix → PROPOSED + gate reason tallied.
- [x] CUJ-02: RAMS at 95% → PROPOSED (`strict_doc_type`).

## 7) Observability & Ops
- AiDecisionLog payload gains `gate_reason`, `gate_auto_confirm`, `human_confirmed_preserved`.
- Support: large ingest may fill Exceptions inbox until PR-E2 triage — expected fail-closed behaviour.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after CI green (STACK_MAX tip-chase).
2. Staging: map one high-confidence doc; confirm `auto_confirm_gate` block.
3. Promote PROD; verify health tip = main tip.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Mass false auto-confirms, or human confirmer stamps erased on remap.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/standards-wave3-pr-e-ingest-ai`
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_e.md`
- Parent LIVE: #1733 @ `583629859ad5`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Hero board / mission / allowlist updated after LIVE
