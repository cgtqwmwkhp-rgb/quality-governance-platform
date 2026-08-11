# Change Ledger (CL-FR-ASSIST-DEPTH-02)

> Base: `origin/main` @ `d0bf093b` (#1723 tip LIVE).
> Vehicle / van checklist grounded intents. Honesty lock unchanged.

## 1) Summary

- **Feature / Change name:** FR-ASSIST-DEPTH-02 — PlantEx Assist vehicle-check fact packs
- **User goal (1–2 lines):** Ops questions about biggest / highest / negative vehicle (van) check issues must answer from the live defect register heatmap — not parrot-echo + “fixed set” refuse.
- **Problem:** Assist closed intents covered incidents / NM / complaints / actions / CS only. Vehicle checklist analytics already expose top failed `check_field` counts; Assist never gathered them, so real ops questions refused.
- **In scope:**
  - Closed intents `vehicle_check_top_failures` + `vehicle_check_defect_summary`
  - Detector for vehicle/van check language (incl. the two complained phrasings)
  - Fact gatherers over `vehicle_defects` (heatmap + open P1–P3 summary), sample refs `VD-{id}` → `/vehicle-checklists`
  - Unit tests for intent map + citation-safe plain formatter
- **Out of scope / deliberately not done:**
  - Open-chat / inventing outside the closed set
  - Layout.tsx / nav
  - Pass-rate % from raw PAMS cache (summary schema stub only)
  - Near-miss / complaint depth packs beyond existing intents
  - Changing refuse copy for unrelated questions
- **Feature flag / kill switch:** Unchanged (`AI_COPILOT_ENABLED` / `AI_COPILOT_INFERENCE_ENABLED`).

## 2) Impact Map (what changed)

- **Frontend:** None
- **Backend:** `copilot_grounding.py` — intents, detector, gatherers, SoR path for `vehicle_defect`
- **Tests:** `test_copilot_grounded_inference.py`
- **APIs / schemas / database / flags:** None
- **Docs:** This Change Ledger

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive closed intents only. Existing intents unchanged.
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy:** Revert merge; redeploy prior tip. No schema/flag/data.
- **PII:** Vehicle registration may appear on underlying rows; Assist sample refs use synthetic `VD-{id}` only (no plate in reply refs).

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Vehicle-check “biggest/highest issues” | Ungrounded refuse / parrot | Heatmap figures from `vehicle_defects` |
| Citation honesty | Fail-closed | Unchanged fail-closed |
| Writes via Assist | Forbidden | Unchanged forbidden |
| Outside fixed set | Refuse | Unchanged refuse (non-vehicle) |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** “biggest / highest issues for vehicle checks” → `vehicle_check_top_failures`.
- [x] **AC-02:** “highest incidence of negative vehicle checks” → `vehicle_check_top_failures`.
- [x] **AC-03:** Open / P1 vehicle defect count questions → `vehicle_check_defect_summary`.
- [x] **AC-04:** Deterministic plain facts include a failure (or priority) breakdown table and pass `validate_citations`.
- [x] **AC-05:** Sample refs are `VD-{id}` markdown-linked to `/vehicle-checklists`.
- [x] **AC-06:** Honesty lock unchanged — no writes; out-of-set still refuses; figures only from gatherers.
- [x] **AC-07:** `Layout.tsx` not modified.
- [x] **AC-08:** Change Ledger body present for `pnpm validate:pr-body`.
- [x] **AC-09:** No test skipped or loosened to go green.

## 5) Testing Evidence

Observed locally, not inferred:

- [x] `python3.11 -m pytest tests/unit/test_copilot_grounded_inference.py -q` — **38 passed**
- [x] `black` / `isort` on touched files — clean
- [ ] Full CI / STG / PROD LIVE — after PR; conveyor tip-chase

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Ask biggest/highest vehicle-check issues → grounded heatmap table (not refuse).
- [x] **CUJ-02:** Ask highest incidence of negative vehicle checks → same top-failures intent.
- [x] **CUJ-03:** Ask how many open / P1 vehicle defects → priority summary intent.

## 7) Observability & Ops

- Existing citation-drop warning retained for LLM phrasing path.
- No new metrics.

## 8) Release Plan

1. Merge after CI green (admin-merge authorised).
2. Main CI → STG → PROD with `release_sha` = tip.
3. Spot-check Assist (inference on): vehicle-check questions return heatmap figures.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** Incorrect vehicle figures vs Van Checklists analytics heatmap; citation failures storm.
- **Rollback steps:** Revert merge commit; redeploy prior tip. No DB unwind.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Unit: intent map for complained phrasings + citation-safe plain facts
- Change Ledger: this body

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive closed intents only (no schema; honesty lock unchanged)
- [x] **Gate 2:** Tests observed green for touched suite
- [x] **Gate 3:** Rollback = revert deploy (no data migration)
- [ ] **Gate 4:** CI green on PR
- [ ] **Gate 5:** Tip LIVE verified (STG=PROD=MAIN)
