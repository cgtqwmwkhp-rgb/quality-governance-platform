# Change Ledger (CL-FR-ASSIST-NAME-01)

> Base: `origin/main` @ `5cd4a43` (#1707 honesty sweep).
> Product rename + grounded refuse honesty. No alembic.

## 1) Summary

- **Feature / Change name:** FR-ASSIST-NAME-01 — PlantEx Assist rebrand + grounded refuse honesty
- **User goal (1–2 lines):** Every AI surface in PlantExpand is named **PlantEx Assist**. When inference is on, a refused question must not claim the product is a disconnected demo.
- **Problem:**
  1. UI still said “AI Copilot” / “Copilot” while PlantExpand’s common AI name is PlantEx Assist.
  2. PROD correctly discloses grounded mode (`ai_copilot` + `ai_copilot_inference` true → “Live register facts — fixed question set”), but citation/out-of-set refusals still returned “This demo is not connected to your registers…” — so the panel looked unimplemented even when it was live and honest about limits.

> **Honesty note — read before treating PROD output as a bug.**
> If PROD shows the demo banner and “not connected” wording, check
> `AI_COPILOT_INFERENCE_ENABLED` before filing a defect. With inference **off**
> that copy is correct and is `FR-COPILOT-HONEST` working as designed. This PR
> renames the product and corrects the wording on the paths where inference is
> **on**; it does **not** turn inference on, and it changes no flag default.

**Three refusal paths, three different true sentences.** The earlier fix collapsed
these into one string, which is why a live deployment described itself as a
disconnected demo:

| Runtime state | What is actually true | Copy served |
|---|---|---|
| Inference off | No register is read; replies are keyword matches | “This PlantEx Assist demo is not connected to your registers…” |
| Inference on, no answer served | Registers are wired up, so the connection is not the limit. Which limit it is — closed question set, missing caller permission, or module off for the tenant — is deliberately not disclosed | “I cannot answer from live organisation data here, and I will not invent counts… PlantEx Assist answers a fixed set of questions from your registers…” |
| Inference on, citation check failed | Intent matched and figures were computed; the wording quoted something absent from them | “I could not verify every figure in that answer against your own registers, so I have dropped it…” |

**Why the middle row does not blame the question.** `CopilotGroundingService.try_answer`
returns `ungrounded` for an out-of-set question, a permission-gated one the caller may
not read, *and* a module switched off for the tenant — collapsed on purpose, so that a
caller cannot tell which gate closed. One string therefore serves all three, and “that
is outside the fixed set of questions” would be false for two of them. It states the
inability and the no-fabrication promise, and describes the fixed set as a property of
the product rather than as the reason this ask failed.
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
- **Backend:** `copilot_service.py` refuse strings + mode-aware simulator, `copilot.py` disabled detail + action reason, OpenAPI tag “PlantEx Assist” in `src/api/__init__.py` + `src/main.py`
- **Docs:** This Change Ledger; one-line tag edit in `docs/contracts/openapi.json`
- **No alembic / no schema / no new flag**

**Residual technical identifiers, left on purpose.** Renaming any of these is a
breaking change for deployed config, stored rows or client URLs, and none of them
is a string a user reads:

- Route prefix `/api/v1/copilot`; router module `src/api/routes/copilot.py`
- Env / settings `AI_COPILOT_ENABLED`, `AI_COPILOT_INFERENCE_ENABLED`
- Client feature keys `ai_copilot`, `ai_copilot_inference`; kill-switch row `copilot_kill_switch`
- ORM models `CopilotSession` / `CopilotMessage` / `CopilotAction` / `CopilotFeedback` / `CopilotKnowledge` and table names
- React module folder `components/copilot/`, component `AICopilot`, `data-testid`s (`ai-copilot-demo-banner`, `ai-copilot-grounded-banner`), i18n key `nav.copilot`
- Remaining docstrings/log lines that read “AI Copilot” (e.g. `copilot_kill_switch.py`) — developer- and operator-facing only

**`/api/v1/meta/features` does not expose a product name**, and this PR does not
add one. The endpoint returns effective flag state only, and adding a field means
a `ClientFeatureFlagsResponse` schema change plus a contract regeneration — worth
doing deliberately, not as a side effect of a rename. The panel gets its name from
the bundle today, which is accurate because the name is build-time constant.

**`docs/contracts/openapi.json` and `openapi-baseline.json` were edited
surgically (tag string only, one line each), not regenerated.** The checked-in
contract is already stale against `main` by many merged PRs: a full
`scripts/generate_openapi.py` run produced **916 added lines** of drift belonging
to other changes. Importing that into a rename PR would have made the diff
unreviewable and silently claimed those contract changes as this one's.

The two artifacts must move together: `test_openapi_baseline_matches_contracts_artifact`
and `test_paginated_assessment_history_is_published_without_breaking_legacy_array`
both assert the files are equal to each other. (Neither compares against the live
`app.openapi()`, which is why the pre-existing staleness is not itself a failure.)
An earlier commit on this branch changed only the contract and turned that pair
red on CI; both are green now. The rename is non-breaking for
`check_openapi_compatibility.py`, which inspects `paths` and `schemas` and never
`tags`, and no operation carries the tag — only the top-level metadata entry.

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
- [x] AC-10: A citation failure is worded as an unverified figure, **not** as a question outside the fixed set — the intent did match and the figures were computed.
- [x] AC-11: With inference on, **every** fall-through branch (write, risk, unknown concept, navigation, catch-all) drops demo wording, not only the live-data refusal.
- [x] AC-12: The permission-denied and no-intent cases stay indistinguishable from outside — wording keys off a deployment-wide flag, never off the caller.
- [x] AC-13: The grounded live-data refusal makes no claim that is false on the permission-denied or module-off path — it does not assert the question was outside the fixed set, because the same string is served when it was inside it.
- [x] AC-06: `/api/v1/copilot` path and `AI_COPILOT_*` env names are unchanged.
- [x] AC-07: OpenAPI tag for the routes is **PlantEx Assist**.
- [x] AC-08: No alembic revision; no test skipped/loosened to go green.
- [x] AC-09: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

Observed locally, not inferred:

- [x] `pytest tests/unit` — **6507 passed, 0 failed, 11 skipped** (the 11 skips are pre-existing and unrelated)
- [x] `pytest tests/unit -k copilot` — **155 passed, 0 skipped** (covers honesty, grounded inference, grounded compliance, kill switch, feature flag, session scoping, knowledge authz, OpenAPI exclusion)
- [x] `npx vitest run src/components/copilot src/components/__tests__/Layout.test.tsx src/components/__tests__/Layout.a11y.test.tsx src/__tests__/App.test.tsx` — **69 passed**
- [x] `npx tsc --noEmit` — clean
- [x] `npx eslint` on every changed frontend file — clean
- [x] `node scripts/i18n-check.mjs` — 4228 keys validated
- [x] `black --check` clean on the touched Python file (it was already failing at base; this branch does not add to that)

Re-observed after the refusal-copy correction and the rebase onto `main` (#1710):

- [x] `pytest tests/unit/test_copilot_honesty.py tests/unit/test_copilot_grounded_inference.py` — **34 passed**
- [x] `pytest tests/integration/test_copilot_grounded_compliance.py` — **12 passed** (the CI failure reproduced here before the fix)
- [x] `pytest tests/unit/test_gt_openapi_list_routes.py` — **3 passed** (baseline/contract still in lockstep after the rebase)
- [x] `black --check` clean on the three re-touched Python files
- [ ] Full `tests/unit` and the frontend suites — not re-run locally after this correction; CI on this PR is the evidence

New regression tests, each pinned to a sentence that was previously wrong:

- `test_ungrounded_question_refuses_without_claiming_to_be_a_demo` — inference on, out-of-set question: asserts absence of “demo is not connected”, presence of the fixed-set description and of the honest lead clause, and that it does **not** assert the question was outside the set
- `test_ungrounded_write_request_refuses_without_demo_wording` — same for the write-refusal branch
- `test_simulate_refusals_track_whether_the_registers_are_wired_up` — both wordings side by side, asserting the refusal itself (no figure, no invention) is identical either way
- `test_simulate_grounded_fallbacks_never_call_themselves_a_demo` — sweeps all five reachable fall-through branches
- `test_citation_failure_returns_honesty_refusal` — tightened: must say “could not verify”, must **not** point at the fixed question set
- `test_send_message_refuses_a_caller_without_the_permission` (pre-existing, `tests/integration/test_copilot_grounded_compliance.py`) — the guard that caught the first attempt at this rewrite serving a permission-denied caller an out-of-set claim; unchanged, and now green
- `test_flag_off_skips_inference_path` — tightened: demo wording is *retained* where it is true
- `copilotDisclosure.test.ts` “leaves no user-visible ‘Copilot’ wording in any mode” — sweeps every visible field of all three modes

**Not verified here:** no staging or production run; no browser session against a
deployment with inference on. CI on this PR is the first end-to-end evidence.

- [ ] Full PR CI suite — in flight
- [ ] Staging / PROD tip-chase after merge

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: With surface + inference on, header shows PlantEx Assist + grounded banner; refuse outside fixed set does not say “demo”. *(Verified at unit/component level, not in a browser.)*
- [x] CUJ-02: With surface on and inference off, header shows PlantEx Assist (Demo) and demonstration banner — unchanged behaviour, only the name moves.
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
