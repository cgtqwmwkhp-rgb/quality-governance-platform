# Change Ledger (CL-CUJ-DOCUMENTS)

## File allowlist (exclusive)
- `frontend/src/pages/Documents.tsx`
- `frontend/src/pages/__tests__/Documents.test.tsx`
- `frontend/tests/e2e/documents-cuj.spec.ts`
- `scripts/governance/pr_body_cuj_documents.md`

**Zero overlap** with open PRs **#909–#916** (`near_miss*`, `Complaint*`, `RTA*`, `UVDB*`, `ComplianceEvidence*`, `Actions*`, `IMS*`, `syncService.test`, `offlineStorage.test`), Prefer avoid `en.json`/`cy.json`, and **`RiskRegister.tsx`** (parallel sibling may touch Risk). Parked **#853 SMTP/PD** — NEVER invent SMTP/secrets.

## 1) Summary
- **Feature / Change name:** CUJ — Documents library honesty + proof (≥8.5 / aim ~9.5)
- **User goal:** Operators see live vs empty vs unavailable library states honestly, get toasts on load/search/upload/open failures, and never mistake a failed list/search for an empty library or zero matches.
- **In scope:** Toast on list/stats/search/upload/open failures; Live/Partial badges; Documents unavailable empty state (not fake empty); semantic search unavailable panel; Playwright CUJ; unit tests for critical honesty states
- **Out of scope:** SMTP/PagerDuty (#853); sibling CUJ pages (#909–#916); RiskRegister; i18n en/cy (English literals retained to avoid parallel conflicts); LibraryShell edits
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Documents.tsx` honesty UX (toasts, Live/Partial, unavailable vs empty)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** Playwright CUJ + vitest honesty cases
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX/proof only — no API or schema changes
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Failures surface via toast + banner/panel (list, stats, search, upload, open/download) — never silent
- [x] AC-02: List/search unavailable labeled distinctly from empty library / zero matches
- [x] AC-03: Live data badge when list+stats succeed; Partial badge when one source fails

## 5) Testing Evidence (link to runs)
- [x] Lint — CI Code Quality gate
- [x] Typecheck — CI Build Check
- [x] Build — CI Build Check
- [x] Unit tests — `Documents.test.tsx` (live badge, list unavailable, stats partial, search unavailable, open toast)
- [x] Integration tests — N/A (FE-only)
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — `frontend/tests/e2e/documents-cuj.spec.ts`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Live Documents library → Live data badge → document card visible (not empty)
- [x] CUJ-02: List API failure → Partial badge + Documents unavailable (not fake empty library)
- [x] CUJ-03: Stats API failure → list remains live + Partial badge/warning
- [x] CUJ-04: Semantic search failure → Search unavailable (not zero matches)

## 7) Observability & Ops
- **Logs:** Existing `trackError` retained; toast announces failures assertively
- **Metrics:** No new backend metrics
- **Alerts:** No change
- **Runbook updates:** N/A — FE honesty + proof only

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Local:** Allowlisted edits on exclusive branch `path10/cuj-documents-honesty`
- **Staging verification:** tip SHA + `/healthz` 200 (2×) after CI deploy
- **Canary plan:** N/A — standard staging then force_deploy
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==prod

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Toast noise, false partial-data badges, or Playwright false failures on `/documents`
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
