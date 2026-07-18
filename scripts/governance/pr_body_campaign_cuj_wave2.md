# Change Ledger (CL-CAMPAIGN-CUJ-WAVE2)

## 1) Summary
- **Feature / Change name:** Campaign CUJ Wave 2 — portal ask unify, assignment-scoped document URL, reminder email CTA, evidence disposition
- **User goal (1-2 lines):** Harden the engineer campaign journey after Wave 1: portal questions route through the same HSEQ assignment API as My Reading, document PDF access is scoped to active assignments, reminder/overdue emails deep-link to portal reading, and compliance evidence exports include attestation disposition.
- **In scope:** Confirm reminder/overdue in-app `action_url` portal links; best-effort reminder/overdue assignee emails with portal CTA; `GET /document-campaigns/assignments/{id}/document-url`; PortalReading ask → `askAssignmentQuestion`; PortalReading/MyReading Open/Read → assignment document-url; `signature_disposition` on JSON/CSV evidence packs; unit/FE tests; this Change Ledger
- **Out of scope:** Changing global `GET /documents/{id}/signed-url` (DocumentDetail/admin unchanged); weakening Wave 1 attestation model; O-11/O-12/O-14; evidence PDF
- **Feature flag / kill switch:** N/A — additive hardening; reminder/overdue emails remain best-effort

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `PortalReading.tsx`, `MyReading.tsx`, `campaignReadingHelpers.ts`, `documentCampaignClient.ts`, `PortalReading.test.tsx`
- **Backend (handlers/services):** `document_campaign_service.py`, `document_campaign.py` routes/schemas
- **APIs (endpoints changed/added):** `GET /document-campaigns/assignments/{id}/document-url`; reminder/overdue assignee emails (best-effort); evidence JSON/CSV adds `signature_disposition`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AssignmentDocumentUrlResponse`; evidence assignment row disposition field
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** Celery reminder sweep may now send assignee emails (best-effort)
- **Config/env/flags:** Uses existing `FRONTEND_URL` / `settings.frontend_url` for email CTA
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — new endpoint; evidence export adds column/field; emails optional
- **Breaking changes:** None for admin DocumentDetail signed-url; assignees must use assignment-scoped URL for Open/Read
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert deploy only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Reminder and overdue in-app notification kwargs use `/portal/reading?assignment={id}`
- [x] AC-02: Best-effort assignee reminder/overdue emails include portal reading CTA when EmailService available
- [x] AC-03: PortalReading Ask a question calls `documentCampaignApi.askAssignmentQuestion` (same as My Reading)
- [x] AC-04: `GET /document-campaigns/assignments/{id}/document-url` verifies assignee ownership + active assignment before returning signed URL
- [x] AC-05: PortalReading and MyReading Open/Read use assignment document-url endpoint (not global signed-url)
- [x] AC-06: Evidence JSON and CSV exports include `signature_disposition` per assignment
- [x] AC-07: Unit/FE tests cover document-url RBAC, portal ask API, reminder email CTA, evidence disposition

## 5) Testing Evidence (link to runs)
- [x] Unit tests — backend Wave 2 campaign suite green locally
- [x] FE unit — PortalReading tests updated for ask + document-url
- [ ] Full CI — pending this PR
- [ ] Staging / prod smoke — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Engineer receives reminder/overdue notification or email → portal reading deep link
- [x] CUJ-02: Engineer Open/Read from portal or My Reading → assignment-scoped signed PDF URL
- [x] CUJ-03: Engineer asks HSEQ question from portal → assignment question thread (not knowledge-bank-only path)
- [x] CUJ-04: HSEQ exports evidence pack → disposition visible for audit

## 7) Observability & Ops
- **Logs:** Best-effort campaign email failures logged; document-url rejects logged via standard API errors
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Trigger reminder sweep or launch campaign; verify portal ask, Open/Read, evidence export disposition
- **Canary plan:** N/A
- **Prod post-deploy checks:** Assignee Open/Read works; admin DocumentDetail preview unchanged

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Assignee cannot open documents or ask questions; email spam/regressions
- **Rollback steps:** Revert squash merge on main; redeploy previous tip
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): pending PR
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
