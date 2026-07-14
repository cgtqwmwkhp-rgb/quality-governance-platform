# Change Ledger (CL-CUJ-A11-FINDING-LOOP-CONSOLE)

## File allowlist (exclusive)
- `frontend/src/pages/Audits.tsx`
- `frontend/src/pages/ActionDetail.tsx`
- `frontend/src/components/audit/FindingLoopStatusRibbon.tsx` (NEW)
- `frontend/src/components/audit/__tests__/FindingLoopStatusRibbon.test.tsx` (NEW)
- `frontend/src/api/auditsClient.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/pages/__tests__/Audits.findings-closure.test.tsx` (NEW)
- `frontend/src/pages/__tests__/Audits.test.tsx` (actionsApi mock only)
- `frontend/src/pages/__tests__/ActionDetail.test.tsx`
- `frontend/tests/e2e/finding-closure-console-cuj.spec.ts` (NEW)
- `scripts/governance/pr_body_cuj_audit_finding_loop_console.md`

**Zero overlap** with sibling overnight lanes: `path11/cuj-audit-answer-integrity` (scoring), `path11/cuj-audit-capa-closure-bridge` (capa_service close bridge). FE consumes optional enrichment / Actions APIs and stubs gracefully when absent.

## 1) Summary
- **Feature / Change name:** CUJ-A11 — Inspector Finding Closure & Loop-Status Console (from AR3)
- **User goal:** On `/audits?view=findings`, auditors/supervisors see finding + CAPA + risk loop status, can assign CAPA from the card, and can close the finding with an honest CAPA gate (override with reason).
- **In scope:** FindingLoopStatusRibbon; Audits findings wiring; ActionDetail return-to-finding CTA; auditsClient tolerant loop fields; i18n; Vitest + Playwright proof
- **Out of scope:** audit_service scoring rewrite; capa_service CAPA→finding close bridge; ReportGenerator; Welsh locale expansion
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Audits findings view + ActionDetail CTA + new ribbon component
- **Backend (handlers/services):** None (consumes existing `PATCH /audits/findings/{id}` + Actions list/update/create)
- **APIs (endpoints changed/added):** None — optional request fields (`closure_note`, `closure_override*`) and response enrichment fields are tolerant
- **Schemas/contracts:** FE-only optional fields
- **Database:** None
- **Workflows/jobs/queues:** Playwright CUJ + unit proof
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE only; CAPA list failure → “status unavailable” + require override (never fake clear)
- **Tolerant reader / strict writer applied?** Yes — enrichment fields optional; close payload extras ignored by current API
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Finding card shows live CAPA `display_status` + assignee when `source_type=audit_finding`
- [x] AC-02: Close finding control calls `PATCH /audits/findings/{id}`; toast on failure
- [x] AC-03: Cannot close finding while linked CAPA still open unless supervisor override with reason
- [x] AC-04: Playwright covers ribbon + assign + gated/override close + completed CAPA close
- [x] AC-05: No mock export claims on this path

## 5) Testing Evidence (link to runs)
- [x] Unit — FindingLoopStatusRibbon + Audits.findings-closure + ActionDetail CTA
- [x] E2E — `frontend/tests/e2e/finding-closure-console-cuj.spec.ts`
- [ ] Lint / Typecheck / Build — CI required checks on draft PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-A11: Findings console → loop ribbon → assign CAPA → close (gated / override / after CAPA complete)

## 7) Observability & Ops
- **Logs:** Existing console + toast on failure
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None (FE honesty surface)

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Local:** Allowlisted edits on exclusive branch `path11/cuj-audit-finding-loop-console`
- **Staging verification:** tip SHA + `/healthz` 200 after CI deploy
- **Canary plan:** N/A — standard staging then force_deploy
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==prod

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** False loop-complete, broken findings view, or Playwright false failures
- **Rollback steps:** Revert squash-merge on `main`; redeploy prior tip
- **Owner:** Platform team

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — allowlist only
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack attached

## Test plan
- [ ] `npm test -- FindingLoopStatusRibbon Audits.findings-closure ActionDetail` (frontend unit)
- [ ] `npx playwright test finding-closure-console-cuj.spec.ts`
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
