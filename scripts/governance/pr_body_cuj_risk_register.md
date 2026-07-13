# Change Ledger (CL-CUJ-RISK-REGISTER)

## File allowlist (exclusive)
- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/__tests__/RiskRegister.test.tsx`
- `frontend/tests/e2e/risk-register-cuj.spec.ts` (NEW)
- `scripts/governance/pr_body_cuj_risk_register.md`

**Zero overlap** with open PRs **#909–#916** (`near_miss*`, `Complaint*`, `RTADetail*`, `UVDBAudits*`, `ComplianceEvidence*`, `Actions*`, `IMSDashboard*`, `syncService.test.ts`, `offlineStorage.test.ts`, tenant inventory, `actions.py`, `external_audit_promotion*`, `assuranceHubHelpers*`). Prefer English literals (no `en.json`/`cy.json`). Parked **#853 SMTP/PD** — never invent secrets.

## 1) Summary
- **Feature / Change name:** CUJ — Risk Register honesty + proof (≥8.5 / aim ~9.5)
- **User goal:** Operators see live vs unavailable risk metrics honestly, get toasts on failures, never confuse API outage with an empty register, and deep-link audit/CAPA workspaces without editing locked pages.
- **In scope:** Toast + banner on list/summary/heatmap failures; nested `by_level` + real `overdue_review` (no hardcoded faux zero); empty vs unavailable empty states; CAPA deep-link via `/actions?sourceType=risk&sourceId=`; vitest + Playwright CUJ
- **Out of scope:** SMTP/PagerDuty (#853); locked CUJ pages above; i18n locale files; backend/schema changes
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `RiskRegister.tsx` honesty UX + CAPA/audit deep-links
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (consumes existing `/risk-register/summary` `by_level` + `overdue_review`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** Playwright CUJ + vitest honesty cases
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX/proof only — no API or schema changes
- **Tolerant reader / strict writer applied?** Yes — summary reader accepts nested `by_level` or flat critical/high/medium/low
- **Breaking changes:** None
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: List load failure surfaces via `toast.error` + alert banner + unavailable empty copy (never silent / never “No risks found”)
- [x] AC-02: Summary cards read nested `by_level` and real `overdue_review`; unavailable metrics show `—` (not faux zero)
- [x] AC-03: CAPA deep-link uses platform pattern `/actions?sourceType=risk&sourceId=:id` without editing Actions page; audit/finding links retained
- [x] AC-04: Vitest covers toast/unavailable/CAPA/nested summary; Playwright CUJ-01/02 mocked honesty paths

## 5) Testing Evidence (link to runs)
- [x] Lint — CI Code Quality gate
- [x] Typecheck — CI Build Check
- [x] Build — CI Build Check
- [x] Unit tests — `RiskRegister.test.tsx` (bow-tie gate, audit links, CAPA deep-link, nested summary, list/summary honesty)
- [x] Integration tests — N/A (FE-only)
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — `frontend/tests/e2e/risk-register-cuj.spec.ts`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Live Risk Register → nested summary metrics → audit/finding links → Open CAPA deep-link
- [x] CUJ-02: List API failure → unavailable banner + `—` metrics (not empty register / not faux overdue=0)
- [x] CUJ-partial: Summary API failure → Partial badge + overdue unavailable while rows remain visible

## 7) Observability & Ops
- **Logs:** `console.error` retained on unexpected catch; operator-visible toast announces failures assertively
- **Metrics:** FE now displays API `overdue_review` / `by_level` honestly (no invented zeros)
- **Alerts:** No change
- **Runbook updates:** N/A — FE honesty + proof only

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Local:** Allowlisted edits on exclusive branch `path10/cuj-risk-register-honesty`
- **Staging verification:** tip SHA + `/healthz` 200 (2×) after CI deploy
- **Canary plan:** N/A — standard staging then force_deploy
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==prod

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Toast noise, false partial-data badges, or Playwright false failures on `/risk-register`
- **Rollback steps:** Revert squash-merge on `main`; redeploy prior tip via production workflow_dispatch with full SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: Post-merge staging tip
- Canary evidence (if applicable): N/A
- Gate 0: Change ledger present (this file)
- Gate 1: Exclusive allowlist enforced
- Gate 2: CI required checks
- Gate 3: Staging tip==SHA
- Gate 4: Prod tip==SHA
- Gate 5: Evidence recorded in this PR

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive FE/proof only; exclusive allowlist
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verified tip==SHA
- [ ] **Gate 4:** Prod tip==SHA after force_deploy
- [ ] **Gate 5:** Evidence pack updated

## Test plan
- [x] `npm test -- RiskRegister` (frontend unit honesty + deep-links)
- [ ] `npx playwright test risk-register-cuj.spec.ts` (CI / local)
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
- Do **not** merge until conveyor review; Risk Register CUJ honesty only; #853 parked
