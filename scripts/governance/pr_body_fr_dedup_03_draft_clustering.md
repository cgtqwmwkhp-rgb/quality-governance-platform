# Change Ledger (CL-FR-DEDUP-03-DRAFT-CLUSTERING)

> Base: `origin/main` @ tip LIVE `fd9f0f07` (#1718). Serial after FR-DEDUP-01d.
> Collapses OCR per-page Compliant floods on import-review.

## 1) Summary

- **Feature / Change name:** FR-DEDUP-03 — OCR draft finding clustering
- **User goal (1–2 lines):** Import-review must not show dozens of identical “Compliant” drafts minted once per page by the keyword scanner.
- **Problem:** `_dedupe_findings` only exact-matched `(title, description[:140])`. Per-page Compliant hits have different descriptions → flood (e.g. 36× same-title Compliant on Achilles shell).
- **In scope:**
  - Cluster by normalized title + clause id when present
  - Cluster positive Compliant / Competent / Effective by title + type
  - Prefer highest confidence; merge pages + snippets; stamp `cluster_size`
- **Out of scope:** Import identity gate (#1719); UVDB purge (01d); post-promote finding twins (ops).
- **Feature flag / kill switch:** N/A — analysis-path behaviour.

## 2) Impact Map

- **Backend:** `src/domain/services/external_audit_analysis_service.py`
- **Tests:** `tests/unit/test_external_audit_analysis_service.py`
- **APIs / DB / flags:** No migration. Draft list shrinks before persist.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive clustering inside existing dedupe.
- **Breaking changes:** None. Distinct observations without shared clause stay separate.
- **Migration plan:** N/A. Existing pending drafts unchanged until re-analyse.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Per-page Compliant flood | N drafts | 1 clustered draft |
| Clause-keyed near-twins | Separate if desc differs | One representative |
| Distinct findings | Kept | Kept (exact key fallback) |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** Multi-page Compliant same title → one draft with merged `source_pages`.
- [x] **AC-02:** Shared clause id + title → one draft; highest confidence wins.
- [x] **AC-03:** Same title, different description, no clause → still two drafts.
- [x] **AC-04:** Change Ledger + Gate Checklist present.

## 5) Testing Evidence

- [x] `pytest tests/unit/test_external_audit_analysis_service.py` — local
- [ ] Full CI after PR open

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Re-analyse Achilles PDF → import-review Compliant flood collapsed.
- [x] **CUJ-02:** Distinct observations without clause remain listed separately.

## 7) Observability & Ops

- Provenance: `cluster_merged`, `cluster_size` on winner

## 8) Release Plan

- Allowlist after 01d LIVE → admin-merge → tip-chase → spot-check import-review

## 9) Rollback Plan

- **Trigger:** Legitimate distinct positives wrongly collapsed.
- **Steps:** Revert squash; redeploy prior tip; narrow cluster triggers if needed.
- **Owner:** Platform / conveyor

## 10) Evidence Pack

- Local unit: clustering tests
- CI / tip LIVE: after merge

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — draft payload additive provenance only
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Rollback = revert
- [~] **UX Coverage Gate:** HOLD — ignored per conveyor instruction
