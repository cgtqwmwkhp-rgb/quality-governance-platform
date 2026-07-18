# Change Ledger (CL-CAMPAIGN-CUJ-WAVE1)

## 1) Summary
- **Feature / Change name:** Campaign CUJ Wave 1 — email CTA, signed PDF open, quiz/signature harden, HSEQ
- **User goal (1-2 lines):** Fix smoke-test blockers so engineers get a useful welcome email with portal deep link, open the policy PDF directly, can complete quizzes (including open questions) with 3 attempts, and use a world-class question gate + conditional signature before completing.
- **In scope:** Launch email HTML + AI/static welcome; in-app `action_url` → `/portal/reading?assignment=`; Open/Read via signed-url; quiz open-type + empty-options harden + max 3 attempts; conditional `signature_disposition`; HSEC→HSEQ user-facing copy; portal pending badges; migration `signature_disposition`; unit/FE tests; this Change Ledger
- **Out of scope:** CUJ Wave 2 (RBAC signed-url tighten, portal ask API unify, reminder email parity); O-11/O-12/O-14; evidence PDF; O-13 key rotation
- **Feature flag / kill switch:** N/A — product harden; launch email AI is best-effort with static fallback

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `PortalReading.tsx`, `MyReading.tsx`, `Portal.tsx`, `PortalWork.tsx`, `campaignReadingHelpers.ts`, `Layout.tsx`, `AdminDashboard.tsx`, i18n en/cy
- **Backend (handlers/services):** `document_campaign_service.py`, `document_campaign_notifications.py`, `document_campaign.py` model/schemas/routes
- **APIs (endpoints changed/added):** Complete accepts `signature_disposition`; quiz submit returns `quiz_attempts` / `attempts_remaining`; Open/Read uses existing `GET /documents/{id}/signed-url`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Complete + quiz response fields; FE client types
- **Database (migrations/entities/indexes):** `campaign_assignments.signature_disposition` nullable String(64) — `20260728_campaign_sig_disp`
- **Workflows/jobs/queues (if any):** None (launch email still best-effort at launch time)
- **Config/env/flags:** Uses existing `FRONTEND_URL` / `settings.frontend_url` for email CTA
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — nullable disposition; clients omit field → server derives
- **Breaking changes:** None for existing completed rows; complete without signature now rejected when no open HSEQ question
- **Migration plan:** Alembic upgrade adds nullable column
- **Rollback strategy (DB):** Downgrade drops column

## 4) Acceptance Criteria (AC)
- [x] AC-01: Launch email includes welcome content + CTA to `/portal/reading?assignment={id}` (AI optional, static fallback)
- [x] AC-02: In-app assignment notification `action_url` points at portal reading with assignment id
- [x] AC-03: Portal/My Reading Open/Read opens signed PDF URL (not `/documents/{id}` landing)
- [x] AC-04: Quiz treats `open`/`open_text`/`text` and empty-option MCQs as open input; max 3 attempts
- [x] AC-05: Complete requires signature when no open question; with open question allows defer or sign-pending disposition
- [x] AC-06: User-facing copy uses HSEQ (not HSEC); portal shows pending attention badge/count
- [x] AC-07: Unit tests cover portal action_url, quiz limits/open types, conditional signature

## 5) Testing Evidence (link to runs)
- [x] Unit tests — backend Wave 1 suite green locally (56 campaign unit tests)
- [x] i18n-check — green locally
- [ ] Full CI — pending this PR
- [ ] Staging / prod smoke — after merge (O-02)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Engineer opens launch email/CTA → portal reading → Open/Read PDF
- [x] CUJ-02: Engineer completes quiz (incl. open Q) within 3 attempts → question gate → sign or defer → complete
- [x] CUJ-03: Portal home shows pending badge when campaign assignments exist; UI says HSEQ

## 7) Observability & Ops
- **Logs:** Best-effort email/AI welcome failures logged; quiz attempt exhaustion returns BadRequest
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Apply migration; launch test campaign; verify email CTA + portal PDF + complete dispositions
- **Canary plan:** N/A
- **Prod post-deploy checks:** tip SHA match; migration applied; O-02 human smoke with real user ID

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Launch/email/complete regressions or migration failure
- **Rollback steps:** Revert squash merge on main; downgrade `20260728_campaign_sig_disp` if needed; redeploy previous tip
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1155
- Staging deploy evidence: Linked after deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
