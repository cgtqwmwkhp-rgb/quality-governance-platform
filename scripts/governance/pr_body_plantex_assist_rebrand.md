# Change Ledger (CL-FR-ASSIST-NAME-01)

> Base: `origin/main` @ `5cd4a43` (#1707 honesty sweep).
> Product rename + grounded refuse honesty. No alembic.

## 1) Summary

- **Feature / Change name:** FR-ASSIST-NAME-01 — PlantEx Assist rebrand + grounded refuse honesty
- **User goal:** Every AI surface in PlantExpand is named **PlantEx Assist**. When inference is on, a refused question must not claim the product is a disconnected demo.
- **Problem:**
  1. UI still said “AI Copilot” / “Copilot” while PlantExpand’s common AI name is PlantEx Assist.
  2. PROD correctly discloses grounded mode (`ai_copilot` + `ai_copilot_inference` true → “Live register facts — fixed question set”), but citation/out-of-set refusals still returned “This demo is not connected to your registers…” — so the panel looked unimplemented even when it was live and honest about limits.
- **In scope:** User-facing strings (disclosure, nav, OpenAPI tag, API detail/refuse copy); grounded refuse rewrite; tests.
- **Out of scope:** Renaming `/api/v1/copilot`, `AI_COPILOT_*` env, DB models, turning inference on/off, expanding the fixed question set.
- **Feature flag / kill switch:** Unchanged (`AI_COPILOT_ENABLED` / `AI_COPILOT_INFERENCE_ENABLED`).

## 2) Impact Map

- FE: `copilotDisclosure.ts`, `AICopilot.tsx`, `Layout.tsx` aria-label, `en.json`/`cy.json` `nav.copilot`
- BE: `copilot_service.py` refuse strings, `copilot.py` disabled detail + action reason, OpenAPI tag “PlantEx Assist”
- Tests: disclosure title, grounded citation refuse must not say demo

## 3) Acceptance

- [x] Header title is PlantEx Assist (Demo when simulated)
- [x] Nav label PlantEx Assist
- [x] Grounded refuse does not contain “demo is not connected”
- [x] Technical paths/flags remain `copilot` / `ai_copilot`

## 4) Test evidence

- pytest: `test_citation_failure_returns_honesty_refusal` + honesty suite — pass
- vitest: `copilotDisclosure.test.ts` + `AICopilot.test.tsx` — 31 pass

## 5) Compliance Delta

- No new personal data processing.
- Disclosure honesty improved (grounded refuse no longer mislabels as demo).
- DPIA still required before broader “inference-true / open chat” claims.

## 6) Risk & Rollback

- Low: string/copy change. Rollback = revert PR.
- Residual: code identifiers still say `copilot` / `ai_copilot` by design.

## 7) DoD

- [x] Change Ledger complete
- [x] Focused unit tests green
- [ ] Tip CI / STG / PROD after merge (conveyor)
