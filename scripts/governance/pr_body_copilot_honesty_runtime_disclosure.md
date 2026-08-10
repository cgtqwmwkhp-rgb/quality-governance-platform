# Change Ledger (CL-COPILOT-HONEST-01/02/03)

## 1) Summary
- **Feature / Change name:** COPILOT-HONEST — the copilot panel discloses what it actually is, from runtime flags
- **Problem:** `AICopilot.tsx` hardcoded “**Demonstration only — no AI model is involved**”, “AI Copilot (Demo)” and “not connected to any AI model”. Since `AI_COPILOT_INFERENCE_ENABLED` shipped, that is false wherever inference is on: a model really does phrase answers over facts this platform computed from the caller’s own registers. A static bundle had no way to know which deployment it was in, so it asserted the same sentence everywhere.
- **User goal:** A user reading the panel is told the truth about the answers they are about to get — off, keyword simulation, or grounded register answers.
- **In scope:** publish `ai_copilot` + `ai_copilot_inference` on the existing `GET /api/v1/meta/features`; derive the panel’s title, subtitle, banner, opening message, input placeholder and “not performed” wording from those flags; grounded-only suggested prompts drawn from the existing closed intent set; backend + frontend tests.
- **Out of scope:** no new intents, no copilot write path, no Azure flag changes, no change to who can see the surface (`isAICopilotDemoEnabled()` still mounts it), no new session/message API fields.
- **Feature flag / kill switch:** `AI_COPILOT_ENABLED`, `AI_COPILOT_INFERENCE_ENABLED`, `copilot_kill_switch` — all pre-existing. Nothing is flipped by this PR; defaults stay closed, so the panel’s wording is byte-identical to today in every environment that has not opted in.

## 2) Impact Map (what changed)
- **Backend / APIs / DB:**
  - `src/domain/features/catalogue.py` — registers `ai_copilot` (`ai_copilot_enabled` + `copilot_kill_switch`) and `ai_copilot_inference` (`ai_copilot_inference_enabled` + `copilot_kill_switch`, requiring `ai_copilot`). Adds one optional field, `requires_ui_key`, for a flag that is a *second* opener on top of a master switch.
  - `src/domain/features/evaluator.py` — folds `requires_ui_key` against the verdict already reached for the prerequisite, so the shared kill switch is read once and the two answers cannot come from different moments.
  - No route, schema or migration change. `GET /api/v1/meta/features` still returns `Dict[str, bool]`, so the published OpenAPI contract is unchanged.
- **Frontend:**
  - `frontend/src/components/copilot/copilotDisclosure.ts` (new) — the single place the panel’s self-description lives: mode resolution plus copy for `unavailable` / `simulated` / `grounded`.
  - `frontend/src/components/copilot/AICopilot.tsx` — reads the two flags through the existing `useFeatureFlag`; title, subtitle, banner, welcome, placeholder and the not-performed label all come from the resolved mode. “(Demo)” is dropped once grounded.
  - `frontend/src/hooks/useFeatureFlag.ts` — both flags declared default-false.
- **Config/env/flags:** none added.
- **Dependencies:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive on both sides. Two new keys on a map response; the frontend falls back to `false` for a backend that has not deployed yet, which resolves to the existing demo wording. An older bundle against the new backend simply ignores the new keys.
- **Direction of every default:** every unknown resolves to the *smaller* claim. Flags arrive asynchronously and default false, so a grounded deployment briefly describes a simulator on first render; overstating is the defect being fixed, understating is a wording lag.
- **Breaking changes:** none.
- **Migration plan:** N/A — no schema change.
- **Rollback strategy (DB):** N/A — revert the PR.

## 4) Compliance Delta
- **Disclosure posture:** improves. The UI stops asserting “no AI model is involved” in deployments where one is. The grounded banner states only properties the server enforces: closed intent set, every reference number and figure validated against the computed facts, and no write path.
- **Data protection:** no new processing, no new recipient, no new personal-data flow. `src/core/ai_provider_disclosure.py` (Art. 28/30 sub-processor SSOT) is untouched — Anthropic/OpenAI already declare `copilot_grounding.py` among their code paths.
- **Access control:** unchanged. Copilot routes still require authentication and still 404 when closed. The two flags carry no permission gate because no copilot permission token exists to fold; each discloses only that this deployment opted the surface in, which its own 404s already reveal.
- **Kill switch:** strengthened. `copilot_kill_switch` now withdraws the panel’s capability claim as well as 404ing the API, instead of leaving the UI advertising a killed feature.
- **Residual risk (recorded, not fixed here):** `useFeatureFlag` honours a `localStorage` override, so a user with devtools can make their own panel display grounded wording while the server still refuses. It changes wording only, never server behaviour. Moving the verdict onto the session-create response would remove even that; not done here to keep this PR to disclosure.

## 5) Acceptance Criteria (AC)
- [x] AC-01: `GET /api/v1/meta/features` publishes `ai_copilot` and `ai_copilot_inference`, each folding config **and** `copilot_kill_switch`.
- [x] AC-02: `ai_copilot_inference` is never true while `ai_copilot` is false — `AI_COPILOT_INFERENCE_ENABLED` alone reports closed.
- [x] AC-03: With both flags open the panel shows the grounded banner, and “(Demo)” is absent from the title.
- [x] AC-04: With the surface open and inference off, the existing demonstration banner and “AI Copilot (Demo)” title are unchanged.
- [x] AC-05: An observed 404 outranks both flags: no capability banner at all, subtitle “Not enabled here”.
- [x] AC-06: Closed-intent prompts (“How many incidents do we have?”, “Which actions are overdue?”) are offered only in grounded mode.
- [x] AC-07: The opening message is rewritten if flags land after the session opens, so it never claims “not connected to any AI model” while a model is answering.
- [x] AC-08: No new intents, no write path, no change to the mount gate.

## 6) Testing Evidence (link to runs)
- [x] Backend unit — `tests/unit/test_client_features_copilot.py` (6 new, gate arithmetic with no DB) + `tests/unit/test_client_feature_catalogue.py` (3 new wiring/ordering tests): **17 passed, local**
- [x] Backend unit — existing copilot suites unaffected (`feature_flag`, `kill_switch`, `grounded_inference`, `honesty`, `openapi_exclusion`): **109 passed, local**
- [x] Backend integration — `tests/integration/test_client_features_endpoint.py` (4 new endpoint cases): **13 passed, local**
- [x] Frontend Vitest — `copilotDisclosure.test.ts` (11 new) + `AICopilot.test.tsx` (7 new, 19 total): **32 passed, local**
- [x] Frontend Vitest — related suites (`Layout`, `App`, `FeatureFlagContext`, hooks, `aiCopilotDemo`): **188 passed, local**
- [x] Lint/type — `eslint --max-warnings 0`, `tsc --noEmit`, `black --check`, `isort --check-only`, `flake8`, `mypy src/domain/features`: clean
- [x] No existing test was modified to pass. The 12 pre-existing `AICopilot` tests pass untouched, because the flags default closed and therefore resolve to today’s wording.
- [ ] CI after open

## 7) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Copilot closed (shipped default) → panel wording identical to today; asking a live-data question still gets the refusal.
- [x] CUJ-02: Surface open, inference off → “AI Copilot (Demo)”, amber “Demonstration only — no AI model is involved”, concept prompts only.
- [x] CUJ-03: Surface open, inference on → “AI Copilot”, “Live register facts — fixed question set”, grounded banner, register prompts offered.
- [x] CUJ-04: Kill switch engaged mid-session → API 404s, panel drops every capability claim and shows the unavailable alert.

## 8) Observability & Ops
- No new signals. The two flags are visible in the `GET /api/v1/meta/features` response, which is how an operator can now confirm what the panel is telling users, rather than inferring it from the bundle.
- The banner carries `data-copilot-mode`, so a screenshot in a support ticket states which mode produced it.

## 9) Release Plan (Local → Staging → Canary → Prod)
- Local: suites above.
- Staging: `curl /api/v1/meta/features` and confirm both keys; open the panel and check the banner matches the deployed flags.
- Prod: ships with both flags in their current state, so the visible change in prod is nil until an operator opens the copilot. No canary needed.

## 10) Rollback Plan (Mandatory)
- **Rollback trigger:** the panel describes a mode the deployment is not in, or the meta endpoint regresses for any existing flag.
- **Rollback steps:** revert the squash-merge. Nothing to undo in the database; no migration, no flag flipped. As an immediate mitigation an operator can engage `copilot_kill_switch`, which closes the surface and the disclosure together.
- **Owner:** Platform / Copilot track.

## 11) Evidence Pack (links)
- CI: linked after PR creation.
- Tip base: `8c43d7e16`.
- Gates the disclosure folds, for review: `require_copilot_enabled` (`src/api/routes/copilot.py`), `copilot_inference_is_enabled` (`src/domain/services/copilot_service.py`), `GROUNDED_INTENTS` + citation validation (`src/domain/services/copilot_grounding.py`).

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** BE flags + FE disclosure implemented, tests added, no existing test weakened
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Rollback plan verified (revert-only; kill switch as immediate mitigation)
- [x] **Gate 5:** Evidence pack recorded / LIVE honesty noted

## Exclusive allowlist (this PR)
- `src/domain/features/catalogue.py`
- `src/domain/features/evaluator.py`
- `tests/unit/test_client_feature_catalogue.py`
- `tests/unit/test_client_features_copilot.py`
- `tests/integration/test_client_features_endpoint.py`
- `frontend/src/components/copilot/AICopilot.tsx`
- `frontend/src/components/copilot/copilotDisclosure.ts`
- `frontend/src/components/copilot/__tests__/AICopilot.test.tsx`
- `frontend/src/components/copilot/__tests__/copilotDisclosure.test.ts`
- `frontend/src/hooks/useFeatureFlag.ts`
- `scripts/governance/pr_body_copilot_honesty_runtime_disclosure.md`

Made with [Cursor](https://cursor.com)
