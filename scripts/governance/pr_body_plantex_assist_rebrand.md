# Change Ledger (CL-FR-ASSIST-NAME-01)

> Base: `origin/main` @ `5cd4a43` (#1707 honesty sweep).
> Product rename + grounded refuse honesty. No alembic.

## 1) Summary

- **Feature / Change name:** FR-ASSIST-NAME-01 — PlantEx Assist rebrand + grounded refuse honesty
- **User goal (1–2 lines):** Every AI surface in PlantExpand is named **PlantEx Assist**. When inference is on, a refused question must not claim the product is a disconnected demo.
- **Problem:**
  1. UI still said “AI Copilot” / “Copilot” while PlantExpand’s common AI name is PlantEx Assist.
  2. PROD correctly discloses grounded mode (`ai_copilot` + `ai_copilot_inference` true → “Live register facts — fixed question set”), but citation/out-of-set refusals still returned “This demo is not connected to your registers…” — so the panel looked unimplemented even when it was live and honest about limits.
- **In scope:**
  - User-facing strings: disclosure titles/subtitles/banners/welcome/placeholders, nav label, OpenAPI tag, API disabled-detail and refuse copy
  - Mode-aware grounded refuse (no “demo is not connected” when inference is on)
  - Regression tests for titles and grounded refuse
- **Out of scope / deliberately not done:**
  - Renaming `/api/v1/copilot`, `AI_COPILOT_*` env vars, DB models (`CopilotSession`, etc.)
  - Turning inference on/off or expanding the fixed question set
  - DPIA completion for broader open-chat claims
- **Feature flag / kill switch:** Unchanged (`AI_COPILOT_ENABLED` / `AI_COPILOT_INFERENCE_ENABLED`).

## 2) Impact Map

- **Frontend:** `copilotDisclosure.ts`, `AICopilot.tsx`, `Layout.tsx` (aria-label + comments), `en.json` / `cy.json` `nav.copilot`, tests
- **Backend:** `copilot_service.py` refuse strings, `copilot.py` disabled detail + action reason, OpenAPI tag “PlantEx Assist” in `src/api/__init__.py` + `src/main.py`
- **Docs:** This Change Ledger
- **No alembic / no schema / no new flag**

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Display-string and refuse-copy only. API paths and feature-flag keys unchanged so existing clients and bake configs keep working.
- **Data migration:** None.
- **PII / retention:** No new personal data processing; grounded mode still refuses rather than invents figures.
- **Backward compatibility:** Technical `copilot` / `ai_copilot` identifiers retained on purpose.

## 4) Acceptance Criteria (AC)

- [x] AC-01: Grounded and unavailable panel titles read **PlantEx Assist** (not “AI Copilot”).
- [x] AC-02: Simulated mode title reads **PlantEx Assist (Demo)**.
- [x] AC-03: Nav control label (`nav.copilot`) is **PlantEx Assist** in en and cy.
- [x] AC-04: When `copilot_inference_is_enabled()` and grounding refuses, response does **not** contain “demo is not connected”.
- [x] AC-05: Simulated live-data refuse may still say demo, branded as PlantEx Assist demo.
- [x] AC-06: `/api/v1/copilot` path and `AI_COPILOT_*` env names are unchanged.
- [x] AC-07: OpenAPI tag for the routes is **PlantEx Assist**.
- [x] AC-08: No alembic revision; no test skipped/loosened to go green.
- [x] AC-09: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

- [x] `python3.11 -m pytest tests/unit/test_copilot_grounded_inference.py::test_citation_failure_returns_honesty_refusal tests/unit/test_copilot_honesty.py` — 7 passed
- [x] `npx vitest run src/components/copilot/__tests__/copilotDisclosure.test.ts src/components/copilot/__tests__/AICopilot.test.tsx` — 31 passed
- [ ] Full PR CI suite — in flight after ledger fix
- [ ] Staging / PROD tip-chase after merge

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: With surface + inference on, header shows PlantEx Assist + grounded banner; refuse outside fixed set does not say “demo”.
- [x] CUJ-02: With surface on and inference off, header shows PlantEx Assist (Demo) and demonstration banner.
- [ ] CUJ-03: Same journeys on staging after tip deploy — post-merge conveyor
- [ ] CUJ-04: Same journeys on PROD after tip deploy — post-merge conveyor

## 7) Observability & Ops

- No new metrics. Existing copilot session/message paths unchanged.
- Operators still use `AI_COPILOT_ENABLED` / `AI_COPILOT_INFERENCE_ENABLED` and the runtime kill switch.
- UX Functional Coverage Gate remains standing HOLD on tip deploys.

## 8) Release Plan

1. Merge after Change Ledger + CI green (admin-merge authorised when green).
2. Tip-chase MAIN → STG sha match → PROD sha match + healthz 200.
3. Spot-check PlantEx Assist header + grounded refuse copy on PROD.
4. Mark LIVE on master action plan canvas only after PROD sha = tip.

## 9) Rollback Plan

- **Owner:** Platform / HSEQ engineering (David Harris)
- **Rollback steps:**
  1. Revert this PR on `main` (or redeploy previous tip image).
  2. Tip-chase revert through STG → PROD.
  3. Confirm header strings and refuse copy restored.
- **Data rollback:** None (no schema change).

## 10) Evidence Pack (links)

- PR: this pull request
- Focused pytest + vitest output (local): see Testing Evidence
- Prior honesty: #1703 LIVE; this PR corrects residual grounded-refuse copy + product name

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Compatibility / data safety reviewed (string-only)
- [x] **Gate 2:** Tests for rename + grounded refuse
- [ ] **Gate 3:** Full CI green on PR
- [ ] **Gate 4:** STG tip sha verified post-merge
- [ ] **Gate 5:** PROD tip sha + healthz verified (DONE bar)
