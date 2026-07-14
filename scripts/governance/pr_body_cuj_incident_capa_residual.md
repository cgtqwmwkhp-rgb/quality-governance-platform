# Change Ledger (CL-CUJ-INCIDENT-CAPA-RESIDUAL)

## File allowlist (exclusive)
- `frontend/src/components/investigations/handoffLinks.ts`
- `frontend/src/components/investigations/handoffLinks.test.ts`
- `frontend/src/pages/ActionDetail.tsx`
- `frontend/src/pages/__tests__/ActionDetail.test.tsx`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/__tests__/IncidentDetail.test.tsx`
- `frontend/src/pages/InvestigationDetail.tsx`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx`
- `frontend/tests/e2e/incident-investigation-capa-cuj.spec.ts`
- `tests/integration/test_incident_investigation_capa_cuj.py`
- `scripts/smoke/incident_investigation_capa_e2e.py` (NEW)
- `scripts/governance/pr_body_cuj_incident_capa_residual.md`

**Zero overlap** with contested lanes: audits execute Wave A, Layout admin hub, GKB audit-pack, complaints, Actions My Work list filters, SWA. Prefer English literals / existing i18n keys (no `en.json`/`cy.json` edits).

## 1) Summary
- **Feature / Change name:** CUJ — Incident → Investigation → CAPA residual honesty + reverse deep-links (≥8.5)
- **User goal:** Operators never confuse CAPA load failures with “zero linked actions”, always reverse deep-link from ActionDetail to incident/investigation/`capa_incident`, and prove the chain with Vitest + Playwright + integration + smoke.
- **In scope:** Shared `getActionSourceLink`; ActionDetail reverse links; Incident/Investigation CAPA load honesty (`—` + toast, no faux empty); Incident workflow proof strip; capa_incident HTTP proof; smoke harness
- **Out of scope:** Actions My Work filters; complaints; audits execute; GKB; SWA; locale file edits; schema/migrations
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `handoffLinks.ts`, `ActionDetail.tsx`, `IncidentDetail.tsx`, `InvestigationDetail.tsx`
- **Backend (handlers/services):** None (consumes existing CAPA + unified Actions APIs)
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** Playwright CUJ depth + smoke script + integration capa_incident assertion
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX/proof only — no API or schema changes
- **Tolerant reader / strict writer applied?** Yes — CAPA count reader distinguishes loading / failed / live
- **Breaking changes:** None
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: ActionDetail deep-links `incident`, `investigation`, and `capa_incident` (and retains `audit_finding`) via shared helper
- [x] AC-02: IncidentDetail shows workflow proof strip + honest `—` CAPA counts on actions load failure (toast; no faux zero)
- [x] AC-03: InvestigationDetail never claims “No CAPA actions are linked” when actions API failed
- [x] AC-04: Integration proves `/capa` incident source → unified `capa_incident` list + `/actions/by-key`
- [x] AC-05: Playwright covers incident proof strip + ActionDetail reverse deep-links; smoke harness added

## 5) Testing Evidence (link to runs)
- [x] Unit — `handoffLinks.test.ts`, `ActionDetail.test.tsx`, `IncidentDetail.test.tsx`, `InvestigationDetail.test.tsx`
- [x] Integration — `tests/integration/test_incident_investigation_capa_cuj.py` (capa_incident residual)
- [x] E2E Smoke (critical journeys) — `frontend/tests/e2e/incident-investigation-capa-cuj.spec.ts`
- [x] Ops smoke — `scripts/smoke/incident_investigation_capa_e2e.py`
- [ ] Lint / Typecheck / Build — CI required checks on draft PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incident detail → workflow proof → Create/Open CAPA → scoped Actions
- [x] CUJ-02: Investigation detail → honest CAPA counts → scoped Actions
- [x] CUJ-03: ActionDetail reverse deep-link incident / investigation / capa_incident
- [x] CUJ-04: HTTP chain incident → from-record → CAPA (`capa_incident`) → by-key

## 7) Observability & Ops
- **Logs:** Existing `trackError` retained; operator-visible toast announces CAPA load failures
- **Metrics:** No new backend metrics (Wave B `investigations.from_record` retained)
- **Alerts:** No change
- **Runbook updates:** Smoke script for residual chain verification

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Local:** Allowlisted edits on exclusive branch `path11/cuj-incident-capa-residual`
- **Staging verification:** tip SHA + `/healthz` 200 (2×) after CI deploy
- **Canary plan:** N/A — standard staging then force_deploy
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==prod

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** False CAPA-unavailable banners, broken ActionDetail source links, or Playwright false failures
- **Rollback steps:** Revert squash-merge on `main`; redeploy prior tip via production workflow_dispatch with full SHA
- **Owner:** Platform team

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — allowlist only
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack attached

## Test plan
- [ ] `npm test -- handoffLinks ActionDetail IncidentDetail InvestigationDetail` (frontend unit)
- [ ] `npx playwright test incident-investigation-capa-cuj.spec.ts`
- [ ] `pytest tests/integration/test_incident_investigation_capa_cuj.py -q`
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
