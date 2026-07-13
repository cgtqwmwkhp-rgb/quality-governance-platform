# Change Ledger (CL-CUJ-EVIDENCE-HUB)

## File allowlist (exclusive)
- `frontend/src/pages/ComplianceEvidence.tsx`
- `frontend/src/pages/__tests__/ComplianceEvidence.test.tsx`
- `frontend/tests/e2e/compliance-evidence-cuj.spec.ts`
- `scripts/governance/pr_body_cuj_evidence_hub.md`

**Zero overlap** with open PRs #907–#911 (Actions/Incident/IMS/near_miss/Complaint/handoffLinks/investigation services), UVDBAudits/RTA drafting, Dependabot, and parked **#853 SMTP/PD** (NEVER invent SMTP/secrets).

## 1) Summary
- **Feature / Change name:** CUJ — Compliance Evidence hub honesty + proof (≥8.5 / aim ~9.5)
- **User goal:** Operators see live vs unavailable coverage/mappings honestly, get toasts on failures, and deep-link to IMS/Audits via query/href without editing those pages.
- **In scope:** Toast on load/mutation failures; Live/Partial badges; coverage/mappings unavailable empty states (not fake zero); IMS/Audits deep-links; Playwright CUJ; unit tests for critical honesty states
- **Out of scope:** SMTP/PagerDuty (#853); UVDB/RTA pages; IMSDashboard/Audits/Actions page edits; i18n en/cy (English literals retained to avoid #907/#910 conflicts)
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `ComplianceEvidence.tsx` honesty UX + deep-links
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
- [x] AC-01: Failures surface via toast + banner (delete, auto-tag, mappings, full/partial load) — never silent
- [x] AC-02: Coverage/mappings unavailable labeled distinctly from empty/zero; Gap Analysis never claims "No gaps found" when coverage API failed
- [x] AC-03: Deep-links to `/ims` and `/audits?view=findings` (plus clause query variants) without editing IMS/Audits pages

## 5) Testing Evidence (link to runs)
- [x] Lint — CI Code Quality gate
- [x] Typecheck — CI Build Check
- [x] Build — CI Build Check
- [x] Unit tests — `ComplianceEvidence.test.tsx` (live badge, coverage unavailable, delete toast, mappings unavailable, deep-links)
- [x] Integration tests — N/A (FE-only)
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — `frontend/tests/e2e/compliance-evidence-cuj.spec.ts`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Live Evidence hub → Live data badge → IMS/Audits deep-links + audit_finding evidence href
- [x] CUJ-02: Coverage API failure → Partial badge + Coverage unavailable (not fake zero gaps); mappings failure ≠ empty mappings

## 7) Observability & Ops
- **Logs:** Existing error banner retained; toast announces failures assertively
- **Metrics:** No new backend metrics
- **Alerts:** No change
- **Runbook updates:** N/A — FE honesty + proof only

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Local:** Allowlisted edits on exclusive branch `path10/cuj-evidence-hub-proof`
- **Staging verification:** tip SHA + `/healthz` 200 (2×) after CI deploy
- **Canary plan:** N/A — standard staging then force_deploy
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==prod

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Toast noise, false partial-data badges, or Playwright false failures on `/compliance`
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
