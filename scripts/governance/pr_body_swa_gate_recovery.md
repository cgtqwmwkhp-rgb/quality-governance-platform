# Change Ledger (CL-SWA-GATE-RECOVERY)

> Adjacent, not fixed here: the Staging UI Verification gate is a hard gate on
> `Azure Static Web Apps CI/CD` but is not one of the three required PR checks, so a
> main-branch red there blocks production SWA promotion silently. Making it a required
> check (or alerting on it) is a governance change, not this PR.

## 1) Summary
- **Feature / Change name:** SWA gate recovery — realign the inspection CUJ mocks with the AUD-F3 answer contract and the AUD-F5 capture inputs
- **User goal:** The production frontend has not been promoted since 2026-09-02 19:57 UTC. Nine consecutive merges to `main` deployed the API but left the production Static Web App on a stale bundle, because the Staging UI Verification hard gate has failed on every one of them. This restores production UI promotion.
- **In scope:** `frontend/tests/e2e/inspection-capa-risk-cuj.spec.ts` only — the route mocks for the answer write and the question-scoped evidence upload, and the file-input locator
- **Out of scope:** product code; the gate's own workflow definition; making the SWA workflow a required PR check; CRM-LIB `/documents`; CB-UI-5; any flag flip
- **Feature flag / kill switch:** none — test-only change. Kill SHA = current LIVE `068bd8580f67`.

## 2) Impact Map (what changed)
- **Frontend:** no product change. One E2E spec's mocks and one locator.
- **Backend:** none.
- **APIs:** none.
- **Database / flags:** none. No migration.
- **Workflows/jobs:** none changed; `Azure Static Web Apps CI/CD` should go green on `main` and stop skipping `Deploy Production SWA`.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** test-only.
- **Breaking changes:** none.
- **Migration plan:** none.
- **Rollback strategy (DB):** none required.
- **Write-path safety:** no product write path touched. QGP never writes PAMS.

## Compliance Delta
- **Root cause, not symptom:** two real contract drifts, not flake. AUD-F3 (#1837) replaced `POST /audits/runs/{id}/responses` with the idempotent `PUT .../responses/by-question/{questionId}`; the CUJ still watched the POST, so `proof.responseCreated` stayed false — that is the failure from 2026-09-02 22:37 onward. AUD-F5 (#1840) then split capture into a camera input and a library input, so `input[type="file"][accept="image/*"]` became a strict-mode violation and masked the first failure from 2026-09-03 02:29 onward.
- **No test was weakened:** every assertion is retained. `responseCreated` now proves the answer actually reached the server on the current contract, which is strictly stronger than the dead POST watcher it replaced. The question-scoped evidence upload is now asserted explicitly instead of being absorbed by the catch-all `{ ok: true }`.
- **What this PR does not claim:** that the earlier "LIVE" stamps for AUD-F3..F6, AUD-P3 and CB-UI-1..4 covered the frontend. They did not — the API image was live, the production SWA bundle was not.

## 4) Acceptance Criteria (AC)
- [x] AC-01: The CUJ mock answers `PUT /api/v1/audits/runs/{run}/responses/by-question/{questionId}` and sets `responseCreated`, matching the AUD-F3 upsert the execute page actually calls.
- [x] AC-02: The CUJ mock answers `POST /api/v1/audits/runs/{run}/evidence` with an `evidence_asset_id`, matching the AUD-F5 question-scoped capture endpoint.
- [x] AC-03: The fail-evidence attach targets `audit-photo-library-input` by test id, so the camera/library split no longer makes the locator ambiguous.
- [x] AC-04: No assertion removed, relaxed, or skipped; no product file changed.

## 5) Testing Evidence (link to runs)
- [x] E2E — `npx playwright test tests/e2e/inspection-capa-risk-cuj.spec.ts --project=chromium` against `https://purple-water-03205fa03-staging.6.azurestaticapps.net`: 4 passed.
- [x] E2E full suite — same base URL, `npx playwright test --project=chromium`: 36 passed, 1 skipped, 1 flaky (`capa-case-tabs-parity` passed on retry), 0 failed.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor answers NO, is blocked from advancing, attaches a photo from the library, continues, and submits. Findings and actions are generated and the auditor lands on CAPA Actions filtered to the finding.
- [x] CUJ-02: Findings deep-links open CAPA Actions and Risk Register scoped to the finding.
- [x] CUJ-03: Flag-to-risk posts and opens the scoped Risk Register.

## 7) Observability & Ops
- **Logs:** none added.
- **Runbook:** After merge, confirm `Azure Static Web Apps CI/CD` on `main` is success and that `Deploy Production SWA (prod API bake)` ran rather than being skipped. Then confirm the production SWA bundle hash matches staging.

## 8) Release Plan
- **Staging:** already verified — the passing run above was executed against the deployed staging SWA.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip; production SWA `index-*.js` hash equals the staging hash. Entra attestation flag stays false.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** the gate stays red, or production SWA promotion fails after the gate goes green.
- **Rollback steps:** revert the squash. Production SWA returns to its current stale-but-serving bundle; no data change.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- Failing gate evidence: run 33769571446 (job 100696760580) — strict mode violation; run 33700273631 (job 100478307749) — `responseCreated` false
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (test-only; mocks realigned to the shipped AUD-F3 and AUD-F5 contracts; no product change)
- [ ] **Gate 2:** CI green
- [x] **Gate 3:** Staging verification (full E2E suite green against the deployed staging SWA)
- [ ] **Gate 4:** Canary (N/A — test-only)
- [x] **Gate 5:** Production verification plan + monitoring ready
