# Change Ledger (CL-CB-PR6-FLAG-ON-ADR)

> Adjacent, not fixed here: **the deploy workflows never write `COMPETENCE_BOARD_ENABLED`.**
> Neither `deploy-staging.yml` nor `deploy-production.yml` names it in their
> `az webapp config appsettings set` blocks, and it is absent from
> `scripts/infra/env-vars.json`. So the code default is what applies — *unless* an operator
> set the app setting by hand while CB-PR1–PR5 were baking, in which case
> `az webapp config appsettings set` merges and that hand-set `false` survives every deploy
> and still wins over this PR. Verify with
> `az webapp config appsettings list --name app-qgp-prod --query "[?name=='COMPETENCE_BOARD_ENABLED']"`
> and delete the setting if it is there and the board is wanted on. This PR deliberately does
> not add the flag to the deploy blocks: that is exactly the mechanism FB-PR5 used for
> `CUSTOMER_FEEDBACK_KINDS_ENABLED` (#1800), and inventing a second, repo-variable-owned flag
> path in the same PR that flips a default would make the rollback story two things at once.
>
> Also adjacent, not fixed: the `test_document_graph_flag_deploy_persistence.py` argument —
> that a flag on no governed path is undurable — is true of this flag too. Widening that guard
> from the Doc Graph family to every flag is its own slice and would change six workflows.

## 1) Summary
- **Feature / Change name:** CB-PR6 — competence board flag on, ADR-0026 issued vs demonstrated
- **User goal:** The competence read paths built by CB-PR1–PR5 become reachable, and the rule that makes them safe is written down first: PAMS says who is **issued**, QGP says who **demonstrated** it in an assessment it actually ran, Citation says what is **statutory**. Three facts, three owners, and no cell anywhere that QGP can "mark competent".
- **In scope:** `docs/adr/ADR-0026-competence-issued-vs-demonstrated.md` (Accepted); `competence_board_enabled` default `False` → `True`; the catalogue disclosure row, `.env.example` and the frontend fallback comment brought into line; a focused CB-PR6 test file; the three CB-PR1/PR4/PR5 default-off assertions updated to assert the shipped default honestly
- **Out of scope:** any PAMS or Citation write; CompetencyDashboard rewrite; new board UI; Finder / Guardian / Coach; bulk QGP Users; per-person compliance-schedule rows (ADR-0020 kill); Entra attestation; ISO 14001 S0; Voyage V0; Dependabot
- **Feature flag / kill switch:** `COMPETENCE_BOARD_ENABLED` / `FF_COMPETENCE_BOARD` now defaults **true**. `false` remains a **subtract-only** kill: all ten flagged endpoints 404 and the compliance schedule emits no coverage fields and issues no extra query. The flag cannot invent a PAMS write path, because none is implemented. Kill SHA = previous LIVE `4f249e84782f`.

## 2) Impact Map (what changed)
- **Frontend:** comment only. `competence_board` stays `false` in `FEATURE_FLAG_DEFAULTS` — that entry is the pre-`/meta/features` fallback, not the flag, and FB-PR5 left `customer_feedback_kinds` closed for the same reason. No component, route or nav changed. CompetencyDashboard is untouched and stays on WDP analytics.
- **Backend:** one default. `src/core/config.py` `competence_board_enabled` `default=False` → `default=True`, same `AliasChoices`, no new field. No route, service or schema changed.
- **APIs:** no new endpoint and no changed response shape. The ten routes on `_enabled_router` (`/board`, `/change-requests` GET+POST, `/assessment-binds` GET+POST+DELETE, `/coverage`, `/coverage-quotas` GET+POST+DELETE) are now reachable by default instead of 404. They were already registered — the board router is mounted unconditionally and the flag was always a request-time dependency — so **the OpenAPI document does not change**.
- **Database / flags:** no migration. No new table, column or index. One flag default.
- **Catalogue:** `CLIENT_FEATURES` `competence_board` reason now says "Default on (CB-PR6, ADR-0026); …=false still subtracts" instead of "Default off … Enable via". The row itself, its `settings_attr` and its `engineer:update` permission are unchanged.
- **Workflows/jobs:** none. The hourly `sync-pams-competence` beat is unchanged; it was already running and only ever SELECTs.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** additive reachability only. Every response body, status code and permission on the competence path is byte-identical to `4f249e84782f` once the flag is open; the only change is that a caller with `engineer:update` gets the payload instead of a 404.
- **Breaking changes:** none for clients. The behaviour change for an *operator* is the point of the PR: an environment that relied on the absent env var meaning "off" now means "on".
- **Migration plan:** none. `alembic` head is unchanged at `20260901_comp_cov`.
- **Rollback strategy (DB):** nothing to roll back — no schema change. Set `COMPETENCE_BOARD_ENABLED=false` and the surface subtracts immediately without a deploy.
- **Write-path safety:** unchanged and re-asserted. `pams_competence_snapshot_service` only ever SELECTs `vw_plantex_engineercompetence`; the assessment overlay's existing guard monkeypatches `_build_pams_engine` and `fetch_pams_competence_rows` to raise, so a bound assessment that opened a PAMS connection would fail the suite. A fail outcome opens an IT-Admin plant revoke request; it does not delete issuance. No Users are created for Atlas people.

## Compliance Delta
- **ISO 45001 7.2 / ISO 9001 7.2 (competence):** the organisation determines competence, retains documented information as evidence, and acts where it is missing. This PR makes the three retained evidence sets *readable together without merging them*: PAMS holds issuance and IT-Admin maintains it; Citation holds statutory training and the HR Advisor maintains it; QGP holds the assessment it ran. Retaining evidence is not the same as being the register of record for it, and ADR-0026 point 2 is what keeps a QGP pass from reading as authorisation to operate plant.
- **ADR-0020:** held. Coverage stays a location duty as a second fact on the existing obligation; no per-person schedule row is created by this PR or reachable from it.
- **ADR-0026 (new):** issued vs demonstrated vs statutory; QGP never writes PAMS or Citation; the flag is subtract-only and cannot open a write path.
- **What this PR does not claim:** that the board replaces CompetencyDashboard (it does not, and no new UI ships here); that a demonstrated pass authorises anyone (only PAMS issues); that an empty overlay means "not competent" (it means no bound assessment has completed, and it stays absent rather than grey); that production is on until the ACA/App Service image is verified at the tip SHA **and** no hand-set `COMPETENCE_BOARD_ENABLED=false` remains; that Entra, ISO 14001 S0 or Voyage V0 moved.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `Settings.model_fields["competence_board_enabled"].default is True`. Asserted on the field default, not the live instance, so an ambient env var cannot decide the test.
- [x] AC-02: `false` still kills. All ten flagged path/method pairs answer **404 with `DISABLED_DETAIL`** through a real request against the real router, parametrised one case per route. Proven to have teeth: with the flag open the same unauthenticated request answers **401**, so the 404 is the flag and not a missing route.
- [x] AC-03: 404 is the *first* verdict. The requests carry no token and can open no session, so the flag is confirmed to resolve before auth, tenant and database — a closed board does not leak that it exists.
- [x] AC-04: every kill-switch name still reaches the field — `AliasChoices` is asserted to be exactly `COMPETENCE_BOARD_ENABLED`, `FF_COMPETENCE_BOARD`, `competence_board_enabled` (in that order, because pydantic resolves first-match-wins), and a fresh `Settings()` reads `False` with each of the three set to `false` and `True` with each set to `true`. The test clears all three aliases first, so an ambient `COMPETENCE_BOARD_ENABLED` on a runner cannot shadow the `FF_` case and turn the test into a report on the machine.
- [x] AC-05: the flagged router carries **exactly** the ten expected routes, asserted by flattening `include_router` mounts (`_iter_api_routes`, as CB-PR4/PR5 — lockfile FastAPI 0.140.7 wraps includes as `_IncludedRouter` with no `.path`; local is 0.135.2). An eleventh surface appearing here fails the test.
- [x] AC-06: ADR-0026 exists, is `Accepted`, dated `2026-09-02`, names its decision makers, and states in terms: issued is PAMS's fact, demonstrated is QGP's fact, statutory is Citation's fact, QGP "never issues an INSERT, UPDATE or DELETE against a PAMS" row, "a pass writes nothing to PAMS", ADR-0020 stands, and the CompetencyDashboard is not replaced. `scripts/check_adr_lifecycle.py` passes 26/26.
- [x] AC-07: no invented surface. Zero new endpoints, zero schema changes, zero migrations, no component or nav change, no `CompetencyDashboard` edit, no Finder/Guardian/Coach, no Users create, no PAMS write, no Entra flip.
- [x] AC-08: the kill tests from CB-PR1–PR5 are all still present and none was weakened — the four monkeypatch-false 404 assertions and the closed-flag schedule-overlay test (which also asserts the closed flag never reaches the database) are unchanged. The three `is False` default assertions were updated to assert the new shipped default, and their function names were changed with them so no test name asserts something its body does not.

## 5) Testing Evidence (link to runs)
- [x] Unit (new) — `tests/unit/test_competence_board_flag_on.py`: **21 passed**.
- [x] Unit (competence + disclosure + FB-PR5 analog) — `test_competence_board_flag_on.py`, `test_pams_competence_snapshot.py`, `test_competence_assessment_overlay.py`, `test_competence_coverage_quorum.py`, `test_competence_change_requests.py`, `test_atlas_competence_board.py`, `test_client_feature_catalogue.py`, `test_feedback_kind.py`: **135 passed, 0 skipped**.
- [x] Unit (blast radius of a default flip) — `tests/unit -k "compliance_schedule or config or feature or meta or flag"`: **757 passed, 1 skipped**. The coverage overlay is the one runtime path a default flip switches on, and it stays bounded: `load_coverage_overlay_async` returns after a single quota SELECT when no quota matches, and the compliance schedule is itself still gated by `compliance_schedule_enabled` default **false**.
- [x] Negative control — with the flag open, an unauthenticated `GET /board` answers 401; with it closed, 404 + `DISABLED_DETAIL`. The kill test is therefore not passing vacuously on a route that does not exist.
- [x] Contract — `tests/contract`: **461 passed, 0 failed, 70 skipped, 56 xfailed, 3 xpassed**. Expected to be untouched and was: the board router is mounted unconditionally and the flag has always been a request-time dependency, so flipping its default changes no OpenAPI path, schema or write-contract baseline. The 70 skips are the pre-existing database-dependent cases and this run is not evidence for those.
- [x] ADR gate — `python3 scripts/check_adr_lifecycle.py`: `[OK] All 26 ADRs pass lifecycle requirements`; `docs/evidence/adr-lifecycle-report.json` regenerated additively (25 → 26, `total_violations` 0), exactly as FB-PR5 committed it.
- [x] Lint / type — `black --check`, `isort --check-only`, `flake8` clean on all six touched Python files; `mypy src/core/config.py src/domain/features/catalogue.py` — `Success: no issues found`.
- [x] Full `tests/unit` — **7267 passed, 10 skipped, 4 failed** in 131s on Python 3.11.15. The four are the known-on-main `gemini_ai` / `gemini_review` upstream breakers, and their cause was read rather than assumed: `ModuleNotFoundError: No module named 'google.genai'`, raised through `tenacity` in the local environment. They touch nothing in this diff and were **not** "fixed" by loosening anything. The **failure set is identical to the CB-PR5 baseline** — the same four named tests, no new failure and none newly skipped. This PR adds 21 tests and removes none; the CB-PR5 ledger's 7244 pass count was not re-measured here, so the exact pass-count delta is not claimed.
- [ ] Frontend — the only change is a comment inside `FEATURE_FLAG_DEFAULTS`; no FE test or type was touched. Vitest/tsc not re-run locally for a comment.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: an IT-Admin with `engineer:update` opens the board on a default deployment and sees issued plant cells from the latest PAMS snapshot, with the stale banner if the hourly beat has not run inside 25 hours. Nothing on the page can write PAMS.
- [x] CUJ-02: a cell with no completed bound assessment shows **no** `demonstrated` value — absent, not a grey "not assessed". The overlay appears only once an assessment bound to that characteristic completes.
- [x] CUJ-03: an assessment recorded as a fail does not remove issuance. It opens a plant revoke request to the IT-Admin mailbox, and the request auto-closes only when a later PAMS snapshot already matches. QGP never made the change.
- [x] CUJ-04: setting `COMPETENCE_BOARD_ENABLED=false` on a running deployment returns the product to `4f249e84782f` behaviour with no deploy — board, coverage, quotas, binds and change requests all 404, and the compliance schedule stops emitting coverage fields and stops issuing the quota query.
- [x] CUJ-05: an operator reading `.env.example` or the `/meta/features` disclosure row now finds "default on … false still subtracts" rather than "default off … enable via", so the shipped state is discoverable without reading `config.py`.

## 7) Observability & Ops
- **Logs:** unchanged. No new log line; the read paths already existed and this PR adds no failure mode of its own.
- **Runbook:** the board is on by default from this SHA. To close it, set `COMPETENCE_BOARD_ENABLED=false` (or `FF_COMPETENCE_BOARD=false`) on the API app setting — no deploy needed, and it takes effect on restart. **Before declaring the board live, check that no hand-set `COMPETENCE_BOARD_ENABLED=false` is sitting on the App Service from the CB-PR1–PR5 bake:** the deploy never writes this key, so a hand-set value survives and silently wins over the code default. The board is read-only in both directions — a wrong PAMS cell is fixed in PAMS by IT-Admin, never in QGP.

## 8) Release Plan
- **Staging:** confirm `GET /api/v1/workforce/competence/board` is reachable (401 unauthenticated, 200 with `engineer:update`) rather than 404; confirm `/coverage`, `/coverage-quotas`, `/assessment-binds`, `/change-requests` likewise; set `COMPETENCE_BOARD_ENABLED=false`, restart, confirm all ten 404 again and that `GET /api/v1/compliance-schedule/requirements` carries no coverage fields; then unset.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip; `az webapp config appsettings list` shows **no** `COMPETENCE_BOARD_ENABLED=false` override; `ENTRA_ATTESTATION_ENABLED` still false; `FF_COMPETENCE_BOARD` not set to false anywhere.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** any write observed against a PAMS or Citation row; any QGP UI offering "mark competent"; a `demonstrated` value appearing on a cell with no completed bound assessment; a per-person compliance-schedule row attributable to competence; any Users row created for an Atlas person; a board response disclosing another tenant.
- **Rollback steps:** set `COMPETENCE_BOARD_ENABLED=false` on the API app setting and restart — this is the whole kill and needs no deploy. If code must go too, revert the squash on `main` and redeploy the previous LIVE SHA `4f249e84782f`. There is no migration to reverse and no data written by this PR.
- **Owner:** David Harris

## 10) Evidence Pack
- ADR: `docs/adr/ADR-0026-competence-issued-vs-demonstrated.md` (Accepted, 2026-09-02)
- ADR gate evidence: `docs/evidence/adr-lifecycle-report.json` (25 → 26 ADRs, 0 violations)
- Flag: `src/core/config.py` — `competence_board_enabled` default `True`, aliases unchanged
- Tests: `tests/unit/test_competence_board_flag_on.py` (21)
- Precedent copied: FB-PR5 #1800 / ADR-0025 — same default-on + subtract-only-kill mechanism, same committed ADR evidence, same closed FE fallback
- Kill SHA: `4f249e84782f`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (no new endpoint, no schema change, OpenAPI unchanged; subtract-only kill proven over HTTP; ADR-0020 held; ADR-0026 recorded; live page untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification (reachable on default; 404 again with the flag false)
- [ ] **Gate 4:** Canary (N/A — flag flip is the release, and it is reversible without a deploy)
- [x] **Gate 5:** Production verification plan + monitoring ready (includes the hand-set app-setting check)
